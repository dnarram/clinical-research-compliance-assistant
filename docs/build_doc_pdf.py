#!/usr/bin/env python
"""Render a Markdown document from docs/ to a DNR-branded A4 PDF.

    uv run python docs/build_doc_pdf.py docs/manual/manual_proyecto_es.md \
        --kind "Manual del proyecto" --subtitle "..." --running "Manual del proyecto"

The Markdown file is the source of truth (it also reads on GitHub); the PDF is the printable
copy, written next to it. Identity follows docs/brand_application.md: Inter for text,
JetBrains Mono for code (the self-hosted files in static/fonts/), navy #162B43 headings,
copper #B95319 as the single accent, flat colours, ComplejoClaro on the light cover.
Headless Google Chrome prints the HTML.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import mistune

REPO = Path(__file__).resolve().parents[1]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONTS = REPO / "static" / "fonts"
LOGO = REPO / "docs" / "brand" / "ComplejoClaro.png"
MARK = REPO / "docs" / "brand" / "SimpleClaro.png"

CSS = """
@font-face { font-family: "Inter"; src: url("__INTER__") format("woff2"); font-weight: 100 900; }
@font-face { font-family: "JetBrains Mono"; src: url("__MONO__") format("woff2"); font-weight: 100 800; }

@page {
  size: A4;
  margin: 22mm 20mm 20mm 20mm;
  @top-left { content: "__RUNNING__"; font: 500 7.5pt "Inter", sans-serif; color: #64748B; }
  @top-right { content: "DNR · David Naranjo Ramírez"; font: 500 7.5pt "Inter", sans-serif; color: #64748B; }
  @bottom-right { content: counter(page); font: 600 8pt "Inter", sans-serif; color: #162B43; }
}
@page :first {
  @top-left { content: none; } @top-right { content: none; } @bottom-right { content: none; }
}

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  margin: 0; font-family: "Inter", Arial, sans-serif; font-size: 10.2pt; line-height: 1.58;
  color: #2C3E50; background: #FFFFFF; font-feature-settings: "ss01" 0;
  hyphens: auto; -webkit-hyphens: auto;
}
p { margin: 0 0 7pt 0; text-align: left; orphans: 3; widows: 3; }
a { color: #B95319; text-decoration: none; hyphens: manual; -webkit-hyphens: manual;
  overflow-wrap: anywhere; }
code { hyphens: manual; -webkit-hyphens: manual; }
strong { color: #162B43; font-weight: 700; }
em { font-style: italic; }

/* --- cover ------------------------------------------------------------------------------ */
.cover { height: 252mm; display: flex; flex-direction: column; justify-content: space-between;
  break-after: page; }
.cover-logo { width: 74mm; height: auto; margin-left: -4mm; }
.cover .eyebrow { font-size: 9pt; font-weight: 700; letter-spacing: 2.4pt; text-transform: uppercase;
  color: #B95319; margin: 0 0 8pt 0; }
.cover h1 { font-size: 30pt; line-height: 1.12; font-weight: 800; color: #162B43; margin: 0 0 12pt 0;
  letter-spacing: -0.3pt; }
.cover .subtitle { font-size: 13pt; line-height: 1.45; color: #2C3E50; max-width: 150mm; }
.cover .rule { border: none; border-top: 2px solid #B95319; width: 34mm; margin: 16pt 0; }
.cover .meta { font-size: 9pt; color: #2C3E50; margin: 0 0 3pt 0; }
.cover .meta strong { color: #162B43; }
.cover .audience { margin-top: 14pt; font-size: 9pt; color: #2C3E50; background: #FAFAFA;
  border: 1px solid #CBD5E1; border-left: 4px solid #B95319; padding: 9pt 12pt; max-width: 150mm; }

/* --- table of contents ------------------------------------------------------------------ */
.toc { break-after: page; }
.toc h2 { break-before: auto; }
.toc ol { list-style: none; padding: 0; margin: 0; }
.toc li.l2 { font-weight: 700; color: #162B43; margin: 7pt 0 2pt 0; font-size: 10.5pt; }
.toc li.l3 { margin: 1pt 0 1pt 14pt; font-size: 9.2pt; color: #2C3E50; }
.toc a { color: inherit; }

/* --- headings --------------------------------------------------------------------------- */
h1, h2, h3, h4 { font-family: "Inter", Arial, sans-serif; color: #162B43; break-after: avoid; }
h1, h2, h3, h4, .cover, .toc, th, figcaption { hyphens: manual; -webkit-hyphens: manual; }
h2 { font-size: 19pt; font-weight: 800; line-height: 1.2; margin: 0 0 12pt 0; padding-bottom: 7pt;
  border-bottom: 2px solid #B95319; letter-spacing: -0.2pt; }
body.chapters h2 { break-before: page; }
h3 { font-size: 12.5pt; font-weight: 700; margin: 16pt 0 6pt 0; }
h4 { font-size: 8.8pt; font-weight: 700; letter-spacing: 1.6pt; text-transform: uppercase; color: #B95319;
  margin: 13pt 0 5pt 0; }

/* --- lists, quotes, code ---------------------------------------------------------------- */
ul, ol { margin: 0 0 8pt 0; padding-left: 15pt; }
li { margin: 0 0 3pt 0; }
li::marker { color: #B95319; }
blockquote { margin: 10pt 0; padding: 9pt 12pt; background: #FAFAFA; border: 1px solid #CBD5E1;
  border-left: 4px solid #B95319; break-inside: avoid; }
blockquote p:last-child { margin-bottom: 0; }
code { font-family: "JetBrains Mono", Menlo, monospace; font-size: 8.6pt; background: #E2E8F0;
  color: #162B43; padding: 0.5pt 3pt; border-radius: 3px; }
pre { background: #E2E8F0; padding: 9pt 11pt; border-radius: 6px; overflow: hidden; break-inside: avoid;
  white-space: pre-wrap; }
pre code { background: none; padding: 0; font-size: 8.4pt; line-height: 1.5; }
hr { border: none; border-top: 1px solid #CBD5E1; margin: 14pt 0; }

/* --- tables ------------------------------------------------------------------------------ */
table { width: 100%; border-collapse: collapse; margin: 6pt 0 11pt 0; font-size: 8.9pt; line-height: 1.42;
  break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #162B43; color: #E2E8F0; font-weight: 600; text-align: left; padding: 5pt 7pt; }
td { padding: 4.5pt 7pt; border-bottom: 1px solid #CBD5E1; vertical-align: top; }
tbody tr:nth-child(even) td { background: #FAFAFA; }

/* --- figures ----------------------------------------------------------------------------- */
figure { margin: 10pt 0 12pt 0; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; max-height: 120mm; border: 1px solid #CBD5E1; border-radius: 4px; }
figure img.narrow { max-width: 62%; }
figcaption { font-size: 8.4pt; color: #2C3E50; margin-top: 5pt; text-align: left; }
figcaption::before { content: "Figura " counter(fig) ". "; font-weight: 700; color: #162B43; }
body { counter-reset: fig; }
figure { counter-increment: fig; }

/* --- footnotes and closing --------------------------------------------------------------- */
section.footnotes { font-size: 8.4pt; border-top: 1px solid #CBD5E1; margin-top: 16pt; }
.closing { margin-top: 26pt; display: flex; align-items: center; gap: 12pt; break-inside: avoid; }
.closing img { width: 26mm; }
.closing p { font-size: 8.4pt; color: #2C3E50; margin: 0; }
"""


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "s"


def render(md_path: Path, args: argparse.Namespace) -> str:
    markdown = mistune.create_markdown(
        escape=False, plugins=["table", "footnotes", "strikethrough", "url"]
    )
    body = str(markdown(md_path.read_text(encoding="utf-8")))
    # The first H1 is the document title: the cover shows it instead.
    body = re.sub(r"^\s*<h1>.*?</h1>", "", body, count=1, flags=re.S)
    # Anything before the first chapter (title block, byline) is the cover's job in print;
    # it stays in the Markdown for readers on GitHub.
    first_h2 = body.find("<h2")
    if first_h2 > 0:
        body = body[first_h2:]

    # Paragraphs holding only an image become numbered figures captioned with the alt text.
    def figure(m: re.Match[str]) -> str:
        attrs = m.group(1)
        alt = re.search(r'alt="([^"]*)"', attrs)
        cls = ' class="narrow"' if "calibration" in attrs or "graph.png" in attrs else ""
        caption = alt.group(1) if alt else ""
        return f"<figure><img{attrs}{cls}><figcaption>{caption}</figcaption></figure>"

    body = re.sub(r"<p><img([^>]*)\s*/?></p>", figure, body)

    toc: list[tuple[int, str, str]] = []
    seen: set[str] = set()

    def heading(m: re.Match[str]) -> str:
        level, inner = int(m.group(1)), m.group(2)
        base = slug(re.sub(r"<[^>]+>", "", inner))
        ident, n = base, 2
        while ident in seen:
            ident, n = f"{base}-{n}", n + 1
        seen.add(ident)
        toc.append((level, ident, inner))
        return f'<h{level} id="{ident}">{inner}</h{level}>'

    body = re.sub(r"<h([23])>(.*?)</h\1>", heading, body, flags=re.S)
    toc_levels = {2} if args.toc_depth == 2 else {2, 3}
    toc_items = "".join(
        f'<li class="l{lvl}"><a href="#{ident}">{inner}</a></li>'
        for lvl, ident, inner in toc
        if lvl in toc_levels
    )

    css = (
        CSS.replace("__INTER__", (FONTS / "Inter-latin.woff2").as_uri())
        .replace("__MONO__", (FONTS / "JetBrainsMono-latin.woff2").as_uri())
        .replace("__RUNNING__", args.running.replace('"', "'"))
    )
    esc = html.escape
    audience = f'<p class="audience">{esc(args.audience)}</p>' if args.audience else ""
    cover = f"""
<section class="cover">
  <div><img class="cover-logo" src="{LOGO.as_uri()}" alt="DNR — David Naranjo Ramírez"></div>
  <div>
    <p class="eyebrow">{esc(args.kind)}</p>
    <h1>{esc(args.title)}</h1>
    <p class="subtitle">{esc(args.subtitle)}</p>
    <hr class="rule">
    <p class="meta"><strong>David Naranjo Ramírez</strong> · {esc(args.date)} · {esc(args.version)}</p>
    <p class="meta">Proyecto final del módulo de IA Generativa · Máster en Data Science &amp; IA · Evolve Academy</p>
    <p class="meta">github.com/dnarram/clinical-research-compliance-assistant</p>
    {audience}
  </div>
</section>"""
    toc_html = f'<section class="toc"><h2>Índice</h2><ol>{toc_items}</ol></section>'
    closing = (
        f'<div class="closing"><img src="{MARK.as_uri()}" alt="DNR">'
        f"<p>Documento elaborado con la identidad visual DNR (manual de marca v2.0). "
        f"Fuente editable: <code>{esc(str(md_path.relative_to(REPO)))}</code>.</p></div>"
    )
    body_class = "chapters" if args.chapters else ""
    return (
        f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f'<base href="{md_path.parent.as_uri()}/">'
        f"<title>{esc(args.title)}</title><style>{css}</style></head>"
        f'<body class="{body_class}">{cover}{toc_html}{body}{closing}</body></html>'
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("markdown", type=Path)
    p.add_argument("--title", default="")
    p.add_argument("--subtitle", default="")
    p.add_argument("--kind", default="Documento")
    p.add_argument("--running", default="", help="running header text (top-left of every page)")
    p.add_argument("--audience", default="", help="optional 'who this is for' box on the cover")
    p.add_argument("--date", default="Noviembre de 2026")
    p.add_argument("--version", default="Versión 1.0")
    p.add_argument("--toc-depth", type=int, default=3, choices=[2, 3])
    p.add_argument("--chapters", action="store_true", help="start every H2 on a new page")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    md_path = args.markdown.resolve()
    if not args.title:
        first = re.search(r"^# (.+)$", md_path.read_text(encoding="utf-8"), flags=re.M)
        args.title = first.group(1).strip() if first else md_path.stem
    args.running = args.running or args.title
    out = (args.out or md_path.with_suffix(".pdf")).resolve()

    with tempfile.TemporaryDirectory(prefix="docpdf-") as tmp:
        page = Path(tmp) / "doc.html"
        page.write_text(render(md_path, args), encoding="utf-8")
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--virtual-time-budget=10000",
                "--allow-file-access-from-files",
                f"--print-to-pdf={out}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    print(f"pdf: {out.relative_to(REPO)} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
