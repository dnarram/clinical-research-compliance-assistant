"""Retrieval over the Chroma collection: scoring, the relevance gate, MMR and citations.

Per question:

1. `similarity_search_with_relevance_scores` gives cosine relevance (1 - distance) for the
   top-k over the whole collection. Its maximum is the **grounding signal**: below the
   calibrated threshold the question is treated as out of scope and the graph routes to
   `refuse` without calling the LLM. This step never uses filters, so the calibration
   stays valid whatever happens next.
2. **Document routing** (optional): if the question names documents ("ICH E6(R3)",
   "Helsinki", "E2A"), the top-k is shared between them with a metadata filter, so a
   "compare X and Y" question gets passages from both instead of whichever document
   happens to score higher. Unnamed questions use plain MMR.
3. `max_marginal_relevance_search` picks the chunks: MMR trades a little similarity for
   diversity across sections and documents.
4. **Context expansion** (optional): each retrieved chunk is widened to its whole section
   when the section is short (a numbered list such as E6(R3) §2.8.10, a Helsinki
   paragraph), else to its neighbouring chunks. A 500-character chunk can cut a list or a
   definition in half — the evaluation showed answers presenting the first four of
   twenty-two consent elements as if complete. Expansion reads the neighbours from the
   collection itself: no API calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from compliance_assistant.config import Settings


@dataclass(frozen=True)
class Source:
    """One passage as shown to the user and referenced as [n] in the answer."""

    n: int
    doc_id: str
    short_cite: str
    section: str
    page: int
    url: str
    text: str
    score: float | None = None
    page_end: int = 0  # > page when an expanded passage spans several pages

    @property
    def citation(self) -> str:
        return cite(
            {
                "short_cite": self.short_cite,
                "section": self.section,
                "page": self.page,
                "page_end": self.page_end,
                "doc_id": self.doc_id,
            }
        )


@dataclass
class RetrievalResult:
    docs: list[Document]  # the chunks retrieval picked (before expansion)
    scores: list[float]
    max_score: float
    grounded: bool
    threshold: float | None
    sources: list[Source] = field(default_factory=list)  # the passages sent to the LLM
    routed_to: list[str] = field(default_factory=list)  # doc_ids named in the question


def cite(meta: dict[str, Any]) -> str:
    """Human citation: 'ICH E6(R3) §2.11.3, p.14', 'ICH E6(R3) §2.8.10, pp.24-26' (with an
    en dash) or 'Declaration of Helsinki (2024) ¶26'."""
    short = meta.get("short_cite", meta.get("doc_id", "?"))
    section = meta.get("section") or ""
    page = meta.get("page")
    page_end = meta.get("page_end") or 0
    if str(meta.get("doc_id", "")).startswith("wma_"):
        return f"{short} ¶{section}" if section else short
    text = f"{short} §{section}" if section else short
    if page and page_end and page_end != page:
        return f"{text}, pp.{page}\u2013{page_end}"
    return f"{text}, p.{page}" if page else text


# --- searches ---------------------------------------------------------------------------


def scored_search(vs: VectorStore, query: str, k: int) -> list[tuple[Document, float]]:
    return vs.similarity_search_with_relevance_scores(query, k=k)


def mmr_search(
    vs: VectorStore, query: str, settings: Settings, k: int | None = None, doc_id: str | None = None
) -> list[Document]:
    kwargs: dict[str, Any] = {
        "k": k or settings.k,
        "fetch_k": settings.fetch_k,
        "lambda_mult": settings.mmr_lambda,
    }
    if doc_id:
        kwargs["filter"] = {"doc_id": doc_id}
    return vs.max_marginal_relevance_search(query, **kwargs)


# --- document routing ----------------------------------------------------------------------


@lru_cache(maxsize=4)
def _aliases(sources_path: Path) -> tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]:
    import yaml

    if not sources_path.exists():
        return ()
    data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    out = []
    for item in data.get("documents", []):
        pats = tuple(re.compile(a, re.I) for a in item.get("aliases", []))
        if pats:
            out.append((item["doc_id"], pats))
    return tuple(out)


def named_documents(question: str, settings: Settings) -> list[str]:
    """doc_ids whose aliases (data/kb/sources.yaml) appear in the question, in order."""
    found = []
    for doc_id, patterns in _aliases(settings.sources_path):
        if any(p.search(question) for p in patterns):
            found.append(doc_id)
    return found


def routed_search(
    vs: VectorStore, query: str, settings: Settings, docs: list[str]
) -> list[Document]:
    """Share the top-k between the named documents (metadata filter). With one named
    document, keep two unfiltered slots so a passage elsewhere can still surface."""
    free = 2 if len(docs) == 1 else 0
    per_doc = max(2, (settings.k - free) // len(docs))
    lists = [mmr_search(vs, query, settings, k=per_doc, doc_id=d) for d in docs]
    if free:
        lists.append(mmr_search(vs, query, settings, k=settings.k))
    merged: list[Document] = []
    seen: set[str] = set()
    for i in range(max((len(x) for x in lists), default=0)):  # round-robin across documents
        for lst in lists:
            if i < len(lst) and lst[i].page_content not in seen and len(merged) < settings.k:
                seen.add(lst[i].page_content)
                merged.append(lst[i])
    return merged


# --- context expansion ------------------------------------------------------------------------


def _join(a: str, b: str) -> str:
    """Concatenate consecutive chunks, removing the splitter's overlap."""
    for size in range(min(80, len(a), len(b)), 9, -1):
        if a[-size:] == b[:size]:
            return a + b[size:]
    return a + "\n" + b


@dataclass
class _Chunk:
    text: str
    meta: dict[str, Any]


class ContextIndex:
    """Every chunk of the collection in document order, grouped into contiguous section
    runs. Built once from the collection (no embedding calls)."""

    def __init__(self, chunks: list[_Chunk], section_budget: int) -> None:
        self.section_budget = section_budget
        self.by_doc: dict[str, list[_Chunk]] = {}
        for c in sorted(
            chunks,
            key=lambda c: (
                c.meta.get("doc_id", ""),
                c.meta.get("page", 0),
                c.meta.get("chunk_index", 0),
            ),
        ):
            self.by_doc.setdefault(str(c.meta.get("doc_id", "")), []).append(c)
        self.pos: dict[tuple[str, int, int], int] = {}
        self.run: dict[tuple[str, int], tuple[int, int]] = {}
        for doc, lst in self.by_doc.items():
            start = 0
            for i, c in enumerate(lst):
                self.pos[(doc, int(c.meta.get("page", 0)), int(c.meta.get("chunk_index", 0)))] = i
                last = i == len(lst) - 1
                if last or lst[i + 1].meta.get("section", "") != c.meta.get("section", ""):
                    for j in range(start, i + 1):
                        self.run[(doc, j)] = (start, i)
                    start = i + 1

    @classmethod
    def from_store(cls, vs: VectorStore, section_budget: int = 4000) -> ContextIndex | None:
        getter = getattr(vs, "get", None)
        if getter is None:
            return None
        try:
            data = getter(include=["documents", "metadatas"])
        except Exception:
            return None
        chunks = [
            _Chunk(text, meta or {})
            for text, meta in zip(
                data.get("documents", []), data.get("metadatas", []), strict=False
            )
            if text
        ]
        return cls(chunks, section_budget) if chunks else None

    def span(self, doc: Document) -> tuple[str, int, int] | None:
        m = doc.metadata
        key = (
            str(m.get("doc_id", "")),
            int(m.get("page", 0) or 0),
            int(m.get("chunk_index", 0) or 0),
        )
        i = self.pos.get(key)
        if i is None:
            return None
        doc_id = key[0]
        lo, hi = self.run[(doc_id, i)]
        lst = self.by_doc[doc_id]
        section_len = sum(len(c.text) for c in lst[lo : hi + 1])
        if lst[i].meta.get("section") and section_len <= self.section_budget:
            return doc_id, lo, hi  # the whole (short) section
        return doc_id, max(lo, i - 1), min(hi, i + 1)  # neighbours within the section

    def render(self, doc_id: str, lo: int, hi: int) -> tuple[str, dict[str, Any]]:
        lst = self.by_doc[doc_id]
        text = lst[lo].text
        for c in lst[lo + 1 : hi + 1]:
            text = _join(text, c.text)
        meta = dict(lst[lo].meta)
        meta["page_end"] = int(lst[hi].meta.get("page", 0) or 0)
        return text, meta


def expand(
    docs: list[Document], scores: list[float], index: ContextIndex
) -> tuple[list[Document], list[float]]:
    """Widen each chunk to its passage and merge hits that land in the same passage.
    Passages keep the rank of their best hit; a chunk unknown to the index is kept as is."""

    @dataclass
    class _Span:
        doc_id: str
        lo: int
        hi: int
        score: float

        def touches(self, other: _Span) -> bool:
            return (
                self.doc_id == other.doc_id
                and self.lo <= other.hi + 1
                and other.lo <= self.hi + 1
                and index.run[(self.doc_id, self.lo)] == index.run[(other.doc_id, other.lo)]
            )

    entries: list[_Span | tuple[Document, float]] = []
    for d, s in zip(docs, scores, strict=True):
        sp = index.span(d)
        if sp is None:
            entries.append((d, s))
            continue
        new = _Span(*sp, s)
        match = next((e for e in entries if isinstance(e, _Span) and e.touches(new)), None)
        if match is None:
            entries.append(new)
        else:
            match.lo, match.hi = min(match.lo, new.lo), max(match.hi, new.hi)
            match.score = max(match.score, new.score)
    out_docs, out_scores = [], []
    for e in entries:
        if isinstance(e, _Span):
            text, meta = index.render(e.doc_id, e.lo, e.hi)
            out_docs.append(Document(page_content=text, metadata=meta))
            out_scores.append(e.score)
        else:
            out_docs.append(e[0])
            out_scores.append(e[1])
    return out_docs, out_scores


# --- the retrieval step ------------------------------------------------------------------------


def retrieve(
    vs: VectorStore,
    query: str,
    settings: Settings,
    threshold: float | None = None,
    index: ContextIndex | None = None,
) -> RetrievalResult:
    """Score and gate (unfiltered), route and diversify, then expand. `threshold=None`
    disables the gate (used before the calibration exists and in tests)."""
    scored = scored_search(vs, query, settings.k)
    scores = [s for _, s in scored]
    max_score = max(scores, default=0.0)
    grounded = threshold is None or max_score >= threshold
    if not grounded:
        return RetrievalResult([], scores, max_score, False, threshold)
    routed = named_documents(query, settings) if settings.doc_routing else []
    docs = routed_search(vs, query, settings, routed) if routed else mmr_search(vs, query, settings)
    by_text = {d.page_content: s for d, s in scored}
    doc_scores = [by_text.get(d.page_content, 0.0) for d in docs]
    passages, passage_scores = docs, doc_scores
    if settings.expand_context and index is not None:
        passages, passage_scores = expand(docs, doc_scores, index)
    result = RetrievalResult(docs, doc_scores, max_score, True, threshold, routed_to=routed)
    result.sources = to_sources(passages, passage_scores)
    return result


def to_sources(docs: list[Document], scores: list[float] | None = None) -> list[Source]:
    out: list[Source] = []
    for i, d in enumerate(docs, start=1):
        m = d.metadata
        out.append(
            Source(
                n=i,
                doc_id=str(m.get("doc_id", "")),
                short_cite=str(m.get("short_cite", "")),
                section=str(m.get("section", "")),
                page=int(m.get("page", 0) or 0),
                url=str(m.get("url", "")),
                text=d.page_content,
                score=(scores[i - 1] if scores else None),
                page_end=int(m.get("page_end", 0) or 0),
            )
        )
    return out


def format_context(sources: list[Source]) -> str:
    """Numbered context blocks for the prompt; the numbers are what the answer cites."""
    blocks = [f"[{s.n}] {s.citation}\n{s.text}" for s in sources]
    return "\n\n".join(blocks)
