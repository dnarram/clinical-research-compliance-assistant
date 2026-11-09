# CLAUDE.md

Guidance for working in this repository.

## What this is

A retrieval-augmented question-answering agent for clinical research compliance:
ICH GCP (E6(R3)), ICH E2A expedited safety reporting and the Declaration of Helsinki,
indexed in ChromaDB with Gemini embeddings and orchestrated as an explicit LangGraph
graph with conversation memory. Final project of the Generative AI module, Master in
Data Science & AI, Evolve Academy. Individual academic work.

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 (pinned in `.python-version`) |
| Environment | `uv` — do not use bare `pip` or `python -m venv` |
| LLM / embeddings | Google Gemini via `langchain-google-genai` (`gemini-3.5-flash-lite`, `gemini-embedding-2`) |
| Vector store | ChromaDB via `langchain-chroma`, persisted under `data/chroma/` |
| Agent | LangGraph `StateGraph` + `InMemorySaver` checkpointer |
| UI | Jupyter notebook (main deliverable) and Streamlit (`app.py`, bonus) |
| Lint + format | `ruff` |
| Tests | `pytest`, fully offline (fake LLM and embeddings) |

## Commands

```bash
uv sync --extra dev                          # create/refresh .venv
uv run pytest                                # offline tests
uv run ruff check . && uv run ruff format .  # lint + format
pre-commit install && pre-commit run --all-files

uv run scripts/00_download_sources.py --record   # fetch PDFs, record sha256
uv run scripts/01_build_kb.py --dry-run           # chunk counts vs quota, no API calls
uv run scripts/01_build_kb.py                     # embed new chunks (needs GEMINI_API_KEY)
uv run scripts/01_build_kb.py --rebuild-only      # Chroma from the versioned cache, no API calls
uv run scripts/02_sanity_retrieval.py             # top-k inspection + threshold calibration
uv run scripts/03_evaluate.py                     # golden set metrics -> docs/evaluation.md
uv run scripts/03_evaluate.py --golden data/eval/heldout.jsonl --with-answers  # held-out set
uv run scripts/05_judge.py --answers data/eval/answers.jsonl            # LLM judge (--model; reported verdicts use gemini-3.5-flash-lite)
uv run python notebooks/build_notebook.py notebooks/compliance_assistant.ipynb  # regenerate the notebook
uv run scripts/chat.py                            # terminal REPL
uv run jupyter lab notebooks/
uv run streamlit run app.py
```

The Gemini key comes from `.env` (`GEMINI_API_KEY=`), Streamlit Cloud secrets or Colab
`userdata`. It is never written in code, notebooks or docs.

## Layout

```
src/compliance_assistant/   importable logic — the only place worth unit-testing
scripts/                    thin CLI entry points, numbered in execution order
notebooks/                  the graded notebook (committed WITH outputs)
tests/                      pytest, offline
data/kb/sources.yaml        knowledge-base inventory (VERSIONED, with sha256)
data/kb/raw/                PDFs (git-ignored; re-fetched by 00_download_sources.py)
data/kb/embeddings/         embedding cache, one jsonl.gz per document (VERSIONED)
data/kb/manifest.json       what was embedded with which model/chunking (VERSIONED)
data/kb/calibration.json    empirically chosen relevance threshold (VERSIONED)
data/chroma/                rebuilt from the cache; git-ignored
data/eval/golden.jsonl      bilingual golden set (25 items) — drafted from verified text, reviewed by David
data/eval/heldout.jsonl     held-out set (12 items), written after v4 was frozen; never tuned on
data/eval/*answers*.jsonl   generated answers + *.judge.jsonl verdicts, committed for audit
docs/                       living documentation; source for README and the demo
```

## Project invariants

1. **The embedding cache is the source of truth, not the Chroma directory.** Chroma's
   on-disk format follows the chromadb version; the jsonl.gz cache does not. Anything
   that needs a vector store calls `vectorstore.build_or_load()`, which rebuilds Chroma
   from the cache with zero API calls.
2. **Ingestion is idempotent.** `manifest.json` records sha256 + embedding model + dim +
   chunking per `doc_id`. A document is re-embedded only when one of those changes.
   Chunk ids are deterministic (`{doc_id}:p{page}:c{idx}:{sha1[:8]}`), so adds are upserts.
3. **Asymmetric embeddings.** Documents are embedded with `task_type=RETRIEVAL_DOCUMENT`
   and queries with `RETRIEVAL_QUERY`. Never share one embeddings instance for both.
4. **The relevance threshold is calibrated, never guessed.** Gemini cosine scores sit in a
   narrow band. `02_sanity_retrieval.py --calibrate` writes `data/kb/calibration.json`
   from the in-domain vs out-of-domain score distributions; `Settings.score_threshold`
   stays `None` unless an explicit override is intended.
5. **The gate reads unfiltered scores.** Document routing (metadata filter) and context
   expansion happen after the refusal decision and must never feed into it.
6. **The graph always retrieves.** Every question goes `rewrite_query -> retrieve ->
   route -> generate | refuse`. The LLM never decides whether to consult the knowledge
   base (the brief requires the KB to be used on every query).
7. **Language policy.** Corpus and prompts are English. Retrieval runs on an English
   standalone question produced by `rewrite_query`; the answer is written in the
   language of the user's question, quoting regulatory text verbatim in English.
8. **Memory window = 10 messages**, applied when building the prompt, not when storing.
   The checkpointer keeps the full thread. The memory demo (Q1, referential Q2,
   "summarise what you told me") must fit inside the window; `tests/test_graph.py`
   pins that.
9. **The golden set is reviewed by David.** `data/eval/golden.jsonl` ground truth (document,
   section) is checked against the indexed text (`tests/test_golden_consistency.py`) and
   reviewed by him. Never auto-generate questions from the corpus, and never loosen a
   keyword to raise a score — only to accept a correct rendering (spelling, Spanish).

## Style

- English for all code, comments, docstrings, documentation, notebook prose and UI.
- Line length 100 (`ruff`). Full type annotations in `src/` and `scripts/`.
- `pathlib.Path` over `os.path`. Comments explain *why*, not *what*.
- Graph nodes log one line each (`[rewrite_query] ...`) so the notebook trace reads
  like the class examples.
- Nothing prints the API key. Print `len(key)` if a sanity check is needed.
- **Spanish mirrors.** `README_es.md` is a translation of `README.md`, and
  `notebooks/compliance_assistant_es.ipynb` is built from the English notebook by
  `notebooks/build_notebook_es.py`. Whenever the English README or notebook changes, update
  the Spanish README and rebuild the Spanish notebook in the same commit.
- **Visual identity = the DNR brand manual** (`docs/brand/ManualIdentidadMarcaDNR_v2.pdf`),
  mapped in `docs/brand_application.md`. Slides, the Streamlit theme, README imagery and
  every chart use only the manual's colours (copper `#B95319` / amber `#E65F19` as the one
  accent, navy `#162B43` as ink, slate `#64748B` for "the rest"), Inter for text and
  JetBrains Mono for code, flat colours (no gradients, glow or shadows), the *Claro* logos
  on light backgrounds and *Oscuro* on dark ones, never pure black. Deck PDF:
  `uv run python docs/slides/build_pdf.py`.
