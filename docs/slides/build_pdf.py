"""Render docs/slides/*.html (the Slides-artifact HTML subset) to a 16:9 PDF with headless Chrome.

Offline fallback for the presentation: `uv run python docs/slides/build_pdf.py [out.pdf]`.
Adds a small shim for the type's custom elements (x-icon, x-connector), hides the <aside>
speaker notes and writes one 1920x1080 page per slide (fonts need network; Arial otherwise).
"""

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

repo = pathlib.Path(__file__).resolve().parents[2]
out_pdf = (
    pathlib.Path(sys.argv[1])
    if len(sys.argv) > 1
    else repo / "docs/slides/clinical-research-compliance-assistant-deck.pdf"
)
root = pathlib.Path(tempfile.mkdtemp(prefix="deck-pdf-"))
deck = json.loads((repo / "docs/slides/deck.json").read_text(encoding="utf-8"))
fonts = "".join(f'<link rel="stylesheet" href="{f["href"]}">' for f in deck["faces"].values())
SHIM = r"""
<script>
const ICONS = {
 Chat: '<path d="M4 5h16v11H9l-5 4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
 Verified: '<path d="M12 2l2.4 2 3.1-.3.9 3 2.6 1.7-1.2 2.9 1.2 2.9-2.6 1.7-.9 3-3.1-.3L12 22l-2.4-2-3.1.3-.9-3L3 15.6l1.2-2.9L3 9.8l2.6-1.7.9-3 3.1.3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M8.5 12.5l2.5 2.5 4.5-5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
 Lightbulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
 Warning: '<path d="M12 3l10 18H2z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 9v5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="17.5" r="1.3" fill="currentColor"/>',
 Lightning: '<path d="M13 2L4 14h7l-1 8 9-12h-7z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
 Book: '<path d="M4 4h7a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4zM20 4h-7a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h7z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
 Users: '<circle cx="9" cy="8" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="17" cy="9" r="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15.5 14.5A5.5 5.5 0 0 1 22 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
};
document.querySelectorAll('x-icon').forEach(el => {
  const body = ICONS[el.getAttribute('name')] || '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/>';
  el.style.display = 'inline-block'; el.style.flex = 'none';
  el.innerHTML = `<svg viewBox="0 0 24 24" width="100%" height="100%">${body}</svg>`;
});
let n = 0;
document.querySelectorAll('x-connector').forEach(el => {
  const [x1, y1, x2, y2] = ['x1', 'y1', 'x2', 'y2'].map(a => parseFloat(el.getAttribute(a)));
  const color = el.style.color || '#000', w = parseFloat(el.style.borderWidth) || 2, id = 'arrow' + (n++);
  const dash = el.style.borderStyle === 'dashed' ? ' stroke-dasharray="12 8"' : '';
  const head = (el.getAttribute('head') || 'end');
  const L = Math.hypot(x2 - x1, y2 - y1), hl = 14, ux = (x2 - x1) / L, uy = (y2 - y1) / L;
  const ex = head === 'none' ? x2 : x2 - ux * (hl - 2), ey = head === 'none' ? y2 : y2 - uy * (hl - 2);
  const sx = head === 'both' ? x1 + ux * (hl - 2) : x1, sy = head === 'both' ? y1 + uy * (hl - 2) : y1;
  Object.assign(el.style, {position: 'absolute', left: '0', top: '0', width: '100%', height: '100%', pointerEvents: 'none'});
  el.innerHTML = `<svg style="position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible"><defs>
    <marker id="${id}" markerUnits="userSpaceOnUse" markerWidth="${hl}" markerHeight="${hl}" refX="${hl - 1}" refY="${hl / 2}" orient="auto"><path d="M0 0 L${hl} ${hl / 2} L0 ${hl} z" fill="${color}"/></marker>
    <marker id="${id}s" markerUnits="userSpaceOnUse" markerWidth="${hl}" markerHeight="${hl}" refX="1" refY="${hl / 2}" orient="auto"><path d="M${hl} 0 L0 ${hl / 2} L${hl} ${hl} z" fill="${color}"/></marker></defs>
    <line x1="${sx}" y1="${sy}" x2="${ex}" y2="${ey}" stroke="${color}" stroke-width="${w}"${dash}
      ${head !== 'none' ? `marker-end="url(#${id})"` : ''} ${head === 'both' ? `marker-start="url(#${id}s)"` : ''}/></svg>`;
});
</script>"""
CSS = """
@page { size: 1920px 1080px; margin: 0; }
html, body { margin: 0; padding: 0; }
body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
section { width: 1920px; height: 1080px; box-sizing: border-box; position: relative; overflow: hidden; page-break-after: always; break-after: page; }
section:last-of-type { page-break-after: auto; break-after: auto; }
section > div, section div { box-sizing: border-box; }
aside { display: none; }
h1, h2, h3, p { margin: 0; }
ul, ol { margin: 0; padding-left: 1.1em; }
li + li { margin-top: 0.25em; }
table { border-collapse: separate; border-spacing: 0; width: 100%; }
td, th { padding: 0.35em 0.6em; border-bottom: 1px solid #dfe3e0; }
"""


def page(sections):
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{deck["title"]}</title>{fonts}'
        f"<style>{CSS}</style></head><body>\n" + "\n".join(sections) + SHIM + "</body></html>"
    )


sections = [(repo / f"docs/slides/{n}.html").read_text(encoding="utf-8") for n in deck["order"]]
for png in (repo / "docs/slides").glob("*.png"):  # logos referenced by <img src> beside the html
    shutil.copy(png, root / png.name)
(root / "deck.html").write_text(page(sections), encoding="utf-8")
for i, s in enumerate(sections, 1):
    (root / f"slide{i}.html").write_text(page([s]), encoding="utf-8")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
base = [
    CHROME,
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--virtual-time-budget=10000",
]
subprocess.run(
    [*base, "--no-pdf-header-footer", f"--print-to-pdf={out_pdf}", f"file://{root / 'deck.html'}"],
    check=True,
    capture_output=True,
)
for i in range(1, len(sections) + 1):
    subprocess.run(
        [
            *base,
            "--window-size=1920,1080",
            f"--screenshot={root}/slide{i}.png",
            f"file://{root}/slide{i}.html",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["sips", "-Z", "960", f"{root}/slide{i}.png", "--out", f"{root}/thumb{i}.png"],
        check=True,
        capture_output=True,
    )
print(
    f"pdf: {out_pdf} ({out_pdf.stat().st_size} bytes, {len(sections)} slides); previews in {root}"
)
