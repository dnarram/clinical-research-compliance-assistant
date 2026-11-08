# Knowledge-base sources

The assistant answers only from the documents below. They are **not redistributed in this
repository**: `scripts/00_download_sources.py` fetches each one from its publisher into
`data/kb/raw/` and verifies the SHA-256 recorded in `data/kb/sources.yaml`, which is the
provenance record. The embedding cache in `data/kb/embeddings/` (versioned) is derived from
these files and is sufficient to run the assistant, the notebook and the Streamlit app
without downloading anything.

| doc_id | Document | Publisher / year | Pages indexed | Chunks | Source URL |
|---|---|---|---|---|---|
| `ich_e2a` | ICH E2A — Clinical Safety Data Management: Definitions and Standards for Expedited Reporting | ICH, 1994 (Step 4, 27 Oct 1994) | 3–12 (cover and history skipped) | 68 | https://database.ich.org/sites/default/files/E2A_Guideline.pdf |
| `ich_e6_r3` | ICH E6(R3) — Guideline for Good Clinical Practice | ICH, 2025 (Step 4, 6 Jan 2025) | 8–86 (cover, history, table of contents skipped) | 665 | https://database.ich.org/sites/default/files/ICH_E6%28R3%29_Step4_FinalGuideline_2025_0106.pdf |
| `wma_helsinki_2024` | WMA Declaration of Helsinki — Ethical Principles for Medical Research Involving Human Participants | World Medical Association, Oct 2024 | web page (37 numbered paragraphs) | 68 | https://www.wma.net/policies-post/wma-declaration-of-helsinki/ |

Total: 3 documents, ~90 pages of substantive text, 801 chunks (500 characters, 50 overlap).

## Attribution and terms of use

- **ICH guidelines** (E2A, E6(R3)) are © International Council for Harmonisation of
  Technical Requirements for Pharmaceuticals for Human Use. ICH permits reproduction of
  its guidelines provided ICH is acknowledged as the source and the text is not altered
  (see the ICH legal notice at <https://www.ich.org/page/legal-notice>). This project
  quotes short passages verbatim, always attributed with document, section and page.
- **WMA Declaration of Helsinki** is © World Medical Association. All intellectual
  property rights are vested in the WMA. The text is published openly at wma.net for
  reference; this project indexes the official web page and quotes paragraphs with their
  number, attributed to the WMA. The 2024 revision (75th General Assembly, Helsinki) is
  the version indexed.

Why the Helsinki web page rather than the PDF: the PDF the WMA site generates from the
page splits paragraph numbers from their text and mangles ligatures ("Clari6cation",
"su=cient"), which corrupts retrieval. The HTML carries the paragraph numbers in
`<ol start="N">` markup, from which `ingestion.load_html` rebuilds "N. …" lines.

## Reproducing the raw files

```bash
uv run scripts/00_download_sources.py          # fetch what is missing, verify all hashes
uv run scripts/00_download_sources.py --force --record   # re-fetch and record new hashes
```

If a publisher changes a file, the hash check fails on purpose. Review the diff before
recording the new hash; a changed source invalidates the cached embeddings for that
document (`data/kb/manifest.json` keys on the hash) and `01_build_kb.py` re-embeds it.
