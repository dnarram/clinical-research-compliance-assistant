"""PDF -> cleaned pages -> chunks with citation metadata.

The regulatory PDFs are text-based (no OCR needed) but noisy in predictable ways:
running headers/footers repeated on every page, words hyphenated across line breaks,
page-number-only lines, and tables of contents. Everything here is deterministic so the
same PDF always yields the same chunk ids, which is what makes the vector store build
idempotent.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, ClassVar

import yaml
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from compliance_assistant.config import Settings

# --- source inventory -------------------------------------------------------------


@dataclass(frozen=True)
class SourceDoc:
    doc_id: str
    title: str
    short_cite: str
    url: str | None
    sha256: str | None = None
    year: int | None = None
    pages: tuple[int, int] | None = None  # 1-based inclusive range to index
    section_style: str = "ich"  # "ich" | "numbered_paragraphs" | "none"
    format: str = "pdf"  # "pdf" | "html"
    licence: str = ""

    def pdf_path(self, settings: Settings) -> Path:
        """Local path of the raw source (name kept for history; also used for HTML)."""
        return settings.raw_dir / f"{self.doc_id}.{self.format}"


def load_sources(settings: Settings) -> list[SourceDoc]:
    raw = yaml.safe_load(settings.sources_path.read_text(encoding="utf-8"))
    docs: list[SourceDoc] = []
    for item in raw["documents"]:
        pages = item.get("pages")
        docs.append(
            SourceDoc(
                doc_id=item["doc_id"],
                title=item["title"],
                short_cite=item["short_cite"],
                url=item.get("url"),
                sha256=item.get("sha256"),
                year=item.get("year"),
                pages=(int(pages[0]), int(pages[1])) if pages else None,
                section_style=item.get("section_style", "ich"),
                format=item.get("format", "pdf"),
                licence=item.get("licence", ""),
            )
        )
    return docs


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --- pages ----------------------------------------------------------------------------


@dataclass
class Page:
    doc_id: str
    page: int  # 1-based, as printed in citations
    text: str


def load_pdf(path: Path, doc_id: str, pages: tuple[int, int] | None = None) -> list[Page]:
    """Extract text page by page with pypdf (the same extractor PyPDFLoader wraps)."""
    reader = PdfReader(str(path))
    first, last = pages or (1, len(reader.pages))
    out: list[Page] = []
    for number in range(first, min(last, len(reader.pages)) + 1):
        text = reader.pages[number - 1].extract_text() or ""
        out.append(Page(doc_id=doc_id, page=number, text=text))
    return out


# --- HTML sources -----------------------------------------------------------------------------

# Blocks that mark the end of the policy text on wma.net pages: the copyright disclaimer,
# the tag cloud and the navigation/cookie banner that follow the last paragraph.
_HTML_STOP_MARKERS = (
    "Disclaimer:",
    "Tags",
    "Read more",
    "Back to policies",
    "Back to Top",
    "Cookie Policy",
)


class _PolicyHtmlParser(HTMLParser):
    """Flatten a policy web page into text lines, re-numbering ordered-list items.

    The WMA publishes the Declaration of Helsinki as HTML where each numbered paragraph is
    an `<li>` inside `<ol start="N">`; the number lives in the markup, not the text. The
    PDF export of the same page mangles ligatures and splits drop caps, so the HTML is the
    cleaner source. Emitted lines: headings verbatim, list items as "N. text", paragraphs
    as-is — which is exactly what `detect_sections(style="numbered_paragraphs")` expects.
    """

    _BLOCK_TAGS: ClassVar[set[str]] = {"p", "h1", "h2", "h3", "h4", "h5", "li", "div", "br", "tr"}
    _SKIP_TAGS: ClassVar[set[str]] = {"script", "style", "nav", "header", "footer", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buf: list[str] = []
        self._skip = 0
        self._ol_next: int | None = None
        self._in_li = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip += 1
        if tag == "ol":
            start = dict(attrs).get("start")
            self._ol_next = int(start) if start and start.isdigit() else 1
        if tag in self._BLOCK_TAGS:
            self._flush()
        if tag == "li" and self._ol_next is not None:
            self._in_li = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        if tag in self._BLOCK_TAGS:
            self._flush()
        if tag == "ol":
            self._ol_next = None

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buf.append(data)

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if not text:
            return
        if self._in_li and self._ol_next is not None:
            text = f"{self._ol_next}. {text}"
            self._ol_next += 1
            self._in_li = False
        self.lines.append(text)

    def close(self) -> None:
        super().close()
        self._flush()


def load_html(
    path: Path, doc_id: str, stop_markers: tuple[str, ...] = _HTML_STOP_MARKERS
) -> list[Page]:
    """A policy web page -> one logical page of numbered paragraphs (page number 1)."""
    parser = _PolicyHtmlParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    lines = parser.lines
    # Keep from the page title onwards and cut at the first navigation marker after it.
    start = next((i for i, ln in enumerate(lines) if ln.lower().startswith("wma declaration")), 0)
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith(stop_markers)),
        len(lines),
    )
    return [Page(doc_id=doc_id, page=1, text="\n".join(lines[start:end]))]


# --- cleaning -----------------------------------------------------------------------------

_PAGE_NUMBER_LINE = re.compile(r"^\s*(page\s+)?[\divx]{1,4}(\s*(/|of)\s*\d{1,3})?\s*$", re.I)
# Table-of-contents entries: "3.16 Data and Records ........................ 39"
_DOTTED_LEADER = re.compile(r"\.{4,}\s*\d{1,3}\s*$")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_MULTISPACE = re.compile(r"[ \t\u00a0]+")  # includes the no-break space pypdf emits
# Drop caps / small caps rendered as a lone letter on its own line: "P\nREAMBLE".
_LONE_LETTER = re.compile(r"(?m)^([A-Z])\n(?=[A-Za-z])")


def _normalise_line(line: str) -> str:
    """Key used to spot running headers/footers.

    Short lines get their digits masked so "Page 3 of 67" == "Page 4 of 67". Longer lines
    are compared verbatim: a sentence that differs only by a number ("...within 7 days"
    vs "...within 15 days") is content, not boilerplate.
    """
    key = line.strip().lower()
    if len(key.split()) <= 5:
        key = re.sub(r"\d+", "#", key)
    return key


def find_repeated_lines(pages: list[Page], min_fraction: float = 0.5) -> set[str]:
    """Lines (digit-normalised) that appear on at least `min_fraction` of the pages.

    Running headers such as "ICH E6(R3) Guideline" or footers like "Page 12 of 67" show
    up on almost every page; genuine content never does. Documents with fewer than 4
    pages are left alone — the statistic is meaningless there.
    """
    if len(pages) < 4:
        return set()
    counts: Counter[str] = Counter()
    for page in pages:
        seen = {_normalise_line(ln) for ln in page.text.splitlines() if ln.strip()}
        counts.update(seen)
    threshold = max(2, int(len(pages) * min_fraction))
    return {key for key, n in counts.items() if n >= threshold and len(key) < 120}


def clean_text(text: str, repeated: set[str] | None = None) -> str:
    """Strip boilerplate and layout artefacts while keeping paragraph breaks."""
    repeated = repeated or set()
    kept: list[str] = []
    previous: str | None = None
    for line in text.splitlines():
        if not line.strip():
            kept.append("")
            previous = None
            continue
        if _PAGE_NUMBER_LINE.match(line) or _DOTTED_LEADER.search(line):
            continue
        if _normalise_line(line) in repeated:
            continue
        line = _MULTISPACE.sub(" ", line).strip()
        # Some generated PDFs (the WMA site exporter) emit every line twice because
        # superscripts are drawn as a second text run. Adjacent duplicates are never
        # legitimate in these documents.
        if line == previous:
            continue
        kept.append(line)
        previous = line
    joined = "\n".join(kept)
    joined = _LONE_LETTER.sub(r"\1", joined)  # "P\nREAMBLE" -> "PREAMBLE"
    joined = _HYPHEN_BREAK.sub(r"\1\2", joined)  # "pharmaco-\nvigilance" -> "pharmacovigilance"
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()


def clean_pages(pages: list[Page]) -> list[Page]:
    repeated = find_repeated_lines(pages)
    return [Page(p.doc_id, p.page, clean_text(p.text, repeated)) for p in pages]


# --- sections -----------------------------------------------------------------------------

# ICH numbering: "2.11.3 Informed consent", "3.16.4", "I. INTRODUCTION", and the E6(R3)
# appendices "A.2.1 Title Page", "B.5 Selection of Participants". A capitalised heading
# word must follow so plain numbers in prose don't match.
_ICH_HEADING = re.compile(
    r"^(\d{1,2}(?:\.\d{1,2}){0,3}|[A-D](?:\.\d{1,2}){1,3}|[IVX]{1,4})\.?\s+(?=[A-Z])"
)
# Declaration of Helsinki: paragraphs are numbered "1." .. "37." at line start.
_PARAGRAPH_HEADING = re.compile(r"^(\d{1,2})\.\s+(?=[A-Z])")


def detect_sections(text: str, style: str, carry: str | None) -> list[tuple[str | None, str]]:
    """Split a page's text into (section, text) runs; `carry` is the last section seen
    on the previous page so chunks on a continuation page still get a section label."""
    if style == "none":
        return [(carry, text)]
    pattern = _ICH_HEADING if style == "ich" else _PARAGRAPH_HEADING
    runs: list[tuple[str | None, list[str]]] = [(carry, [])]
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            runs.append((m.group(1), [line]))
        else:
            runs[-1][1].append(line)
    return [(sec, "\n".join(lines).strip()) for sec, lines in runs if "\n".join(lines).strip()]


# --- chunks -------------------------------------------------------------------------------


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_id(doc_id: str, page: int, index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{doc_id}:p{page}:c{index}:{digest}"


def split_pages(pages: list[Page], source: SourceDoc, settings: Settings) -> list[Chunk]:
    """Recursive character splitting *within* section runs so a numbered requirement is
    never glued to the heading of the next one. Metadata values are str/int only, which
    is what Chroma accepts (None is written as "")."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[Chunk] = []
    carry: str | None = None
    for page in pages:
        runs = detect_sections(page.text, source.section_style, carry)
        index = 0
        for section, run_text in runs:
            carry = section or carry
            for piece in splitter.split_text(run_text):
                piece = piece.strip()
                if len(piece) < 40:  # table fragments, lone headings
                    continue
                chunks.append(
                    Chunk(
                        id=chunk_id(source.doc_id, page.page, index, piece),
                        text=piece,
                        metadata={
                            "doc_id": source.doc_id,
                            "title": source.title,
                            "short_cite": source.short_cite,
                            "page": page.page,
                            "section": section or "",
                            "chunk_index": index,
                            "url": source.url or "",
                        },
                    )
                )
                index += 1
    return chunks


def ingest(source: SourceDoc, settings: Settings) -> list[Chunk]:
    """Source on disk -> cleaned, sectioned, chunked. Pure function of the file bytes."""
    if source.format == "html":
        pages = load_html(source.pdf_path(settings), source.doc_id)
    else:
        pages = load_pdf(source.pdf_path(settings), source.doc_id, source.pages)
    return split_pages(clean_pages(pages), source, settings)


def estimate_chunks(sources: list[SourceDoc], settings: Settings) -> dict[str, int]:
    """Chunk count per document without touching any API — used to sanity-check the
    embedding budget against the free-tier quota before the first real build."""
    return {s.doc_id: len(ingest(s, settings)) for s in sources if s.pdf_path(settings).exists()}
