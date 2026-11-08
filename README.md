# Clinical Research Compliance Assistant

An expert question-answering agent on **Good Clinical Practice (ICH E6(R3))**, **expedited
safety reporting (ICH E2A)** and the **WMA Declaration of Helsinki (2024)**, built with
Google Gemini, ChromaDB and LangGraph. It answers in English or Spanish, quotes the
regulatory text verbatim with section and page, remembers the conversation, and refuses
what its knowledge base does not cover.

Final project of the Generative AI module · Master in Data Science & AI · Evolve Academy ·
David Naranjo Ramírez

> **Live demo:** _Streamlit Cloud URL — added on deployment_ · **Notebook:** [`notebooks/compliance_assistant.ipynb`](notebooks/compliance_assistant.ipynb)

## Why this domain

I spent five years in clinical-trial software support (Medidata Rave, Pfizer and Novo
Nordisk platforms at C3i Solutions / HCLTech) and hold the ICH GCP E6(R2) certificate. The
questions a CRA or a pharmacovigilance associate asks — *is this a SUSAR? how fast must the
sponsor report it? what must the consent form contain? what changed in E6(R3)?* — are
spread across ICH, EU and WMA texts that must be quoted exactly. That is a RAG problem
with a real traceability requirement, and a domain where I can judge whether an answer is
right. It also continues my previous master's project (FAERS GLP-1 pharmacovigilance
pipeline): from the safety data to the rules that govern it.

## What it does

| Capability | How |
|---|---|
| Knowledge base | 3 documents, ~90 pages, **801 chunks** in ChromaDB with `gemini-embedding-2` (768 d) — [`docs/sources.md`](docs/sources.md) |
| Retrieval | Standalone English query → relevance scores → **calibrated refusal gate** → MMR top-6 → numbered passages `[n]` with citation `ICH E6(R3) §2.8.10, p.24` / `Declaration of Helsinki (2024) ¶28` |
| Agent | Explicit LangGraph `StateGraph`: `rewrite_query → retrieve → route → generate \| refuse` |
| Memory | `InMemorySaver` checkpointer per `thread_id`; last 10 messages sent to the model |
| Languages | Answers in the user's language (EN/ES); regulatory wording quoted verbatim in English |
| Interfaces | Notebook chat cell, terminal REPL (`scripts/chat.py`), Streamlit app (`app.py`) |
| Evaluation | Bilingual golden set → retrieval hit-rate@k per language, refusal accuracy, keyword coverage |

## Architecture

```
            ┌──────────────┐    ┌──────────┐    grounded?    ┌──────────┐
 question ─▶│ rewrite_query│───▶│ retrieve │──────yes───────▶│ generate │──▶ answer + sources
            │ (history →   │    │ scores + │                 └──────────┘
            │  standalone  │    │ MMR top-k│───────no───────▶┌──────────┐
            │  English q)  │    └──────────┘                 │  refuse  │──▶ "not in my KB; I cover…"
            └──────────────┘                                 └──────────┘
                  ▲  InMemorySaver checkpoint per thread_id (full history; 10-message window)
```

* **`rewrite_query`** resolves references to earlier turns ("*that* situation", "the same
  rule") and normalises the question to English, the corpus language. It skips the LLM on a
  first English turn.
* **`retrieve`** scores the top-k with cosine relevance; if the best score is under the
  **calibrated threshold** (0.69, from in-domain vs out-of-domain query distributions in
  `data/kb/calibration.json`) the question is out of scope. Otherwise MMR (`k=6,
  fetch_k=24, λ=0.6`) selects passages with coverage across documents.
* **`generate`** gets system prompt v3 + windowed history + numbered passages + the user's
  question and an explicit answer-language line. **`refuse`** is templated (no LLM call).
* Retrieved passages live in graph state, not in `messages`, so the memory window counts
  turns, not context.

Why not `create_agent` with a retriever tool (the "agentic RAG" pattern from class): the
brief requires the knowledge base to be used on **every** query, the free tier makes each
extra LLM call expensive, and a fixed topology is easier to trace and test.

### Knowledge-base build (idempotent, free-tier aware)

The **versioned embedding cache** (`data/kb/embeddings/*.jsonl.gz`) is the source of truth;
the Chroma directory is derived from it in seconds with **zero API calls**. `manifest.json`
records file hash, embedding model, dimension and chunking per document, so nothing is
re-embedded unless one of those changes. Documents use `task_type=RETRIEVAL_DOCUMENT`,
queries `RETRIEVAL_QUERY`. `01_build_kb.py --dry-run` counts chunks against the quota first.

## System prompt and its justification

The prompt in use (`SYSTEM_PROMPTS["v3"]` in [`src/compliance_assistant/prompts.py`](src/compliance_assistant/prompts.py)):

```text
You are a regulatory compliance assistant for clinical research. Your users are clinical
research associates, study coordinators, data managers and pharmacovigilance staff. Your
knowledge base contains: ICH E6(R3) Good Clinical Practice, ICH E2A (definitions and
standards for expedited safety reporting) and the WMA Declaration of Helsinki (2024).

GROUNDING
- Answer only from the numbered context passages. Do not use outside knowledge, even if
  you believe you know the answer.
- Cite the passage that supports each statement with its number in square brackets,
  e.g. "within 7 calendar days [2]". Every factual sentence needs at least one citation.
- If the passages do not contain the answer, say so plainly ("I could not find this in my
  knowledge base"), state what the knowledge base does cover, and stop. Never invent
  section numbers, timelines, definitions or responsibilities.

SOURCES THAT DIFFER
- When passages from different documents (e.g. ICH E6(R3) vs the Declaration of
  Helsinki) address the same point differently, say so explicitly and attribute each
  position to its document. Do not merge them into one claim.

LANGUAGE
- Answer in the language of the user's question (Spanish question -> Spanish answer).
- Quote regulatory wording verbatim in English, in quotation marks, with its citation.
- Keep regulatory terms untranslated: SAE, SUSAR, ADR, IB, IMP, IRB/IEC, CRF, GCP.

SCOPE AND TONE
- Regulatory information, not legal or medical advice; say so if the user asks what they
  should do in a specific case, then explain what the guideline says.
- Stay on clinical-research compliance. For unrelated requests, briefly say it is
  outside your scope.
- Be precise and concise. Prefer the guideline's own terminology.

FORMAT
- Start with the direct answer in one or two sentences.
- Then give the supporting detail (bullets if there are several points).
- Do not add a closing summary or disclaimers unless one of the rules above requires it.
```

| Clause | Design rationale |
|---|---|
| Role, audience, explicit list of the three documents | Fixes register and lets the model say what it does *not* cover |
| Grounding + `[n]` citations on every factual sentence | Traceability is the point of RAG in a regulated setting; numbers map to the sources panel |
| Insufficiency rule ("I could not find this…", list coverage, stop) | The rubric asks how the agent behaves without information; invented article numbers are the worst possible failure |
| Sources that differ → attribute separately | E6(R3) and Helsinki overlap on consent and vulnerable participants but are not identical |
| Language policy | Corpus is English, users are Spanish-speaking; verbatim English quotes keep legal precision |
| Scope and tone | No legal/medical advice; stays on topic |
| Format | Direct answer first; chat-friendly |

**How it evolved** ([`docs/prompt_iterations.md`](docs/prompt_iterations.md)): **v1** was the
bare "answer from the documents" prompt from class — fluent but unattributed, and it
answered out-of-scope questions from general knowledge. **v2** added role, scope and the
insufficiency rule — but merged guidelines into one claim and answered Spanish questions in
English. **v3** added the citation protocol, the handling of differing sources, the
language policy and the output structure. In addition, the user message carries a
deterministic `Reply in English.` / `Responde en español.` line because the prompt rule
alone was not reliable.

## Setup and run

Requirements: Python 3.12, [`uv`](https://docs.astral.sh/uv/), a Gemini API key
(free at <https://aistudio.google.com/apikey>).

```bash
git clone https://github.com/dnarram/clinical-research-compliance-assistant.git
cd clinical-research-compliance-assistant
uv sync --extra dev

cp .env.example .env            # then edit: GEMINI_API_KEY=...

# Knowledge base — the embedding cache is committed, so this makes no embedding API calls:
uv run scripts/01_build_kb.py --rebuild-only

# Chat
uv run jupyter lab notebooks/compliance_assistant.ipynb   # notebook (main deliverable)
uv run scripts/chat.py                                     # terminal
uv run streamlit run app.py                                # web UI
```

Rebuilding the knowledge base from the sources (optional; ~17 embedding requests):

```bash
uv run scripts/00_download_sources.py      # fetch the ICH PDFs and the WMA page, verify sha256
uv run scripts/01_build_kb.py --dry-run    # chunk counts vs quota
uv run scripts/01_build_kb.py              # embeds only what the cache lacks
uv run scripts/02_sanity_retrieval.py --calibrate   # top-k inspection + refusal threshold
```

**Google Colab:** open the notebook, run the first cell (it clones and installs the repo)
and add `GEMINI_API_KEY` under *Secrets*.

**Free tier notes.** Embeddings ≈ 100 requests/min; the build batches 50 chunks per request,
is resumable and backs off on 429. Each chat turn costs 1–2 LLM calls
(`gemini-3.5-flash-lite`; the class default `gemini-2.5-flash-lite` is no longer served to
new keys — override with `LLM_MODEL=` in `.env` if yours differs).

## Example conversations

Executed outputs are in the notebook (section 8). Abbreviated:

| Question | Behaviour |
|---|---|
| *What is the timeline for expedited reporting of a fatal unexpected ADR under ICH E2A?* | "…as soon as possible but no later than 7 calendar days… [2]", follow-up report within 8 additional days — `ICH E2A §1, p.7` |
| *¿Y para las demás reacciones graves e inesperadas, cuál es el plazo?* (same thread) | Rewritten to *"What is the timeline for … other serious and unexpected ADRs under ICH E2A?"* → 15 calendar days `[1]`, answered in Spanish |
| *Summarise in two bullets what you told me so far.* | Two bullets, 7 vs 15 days, both cited — memory across three turns |
| *¿Dice lo mismo la Declaración de Helsinki sobre ese tema?* (after a consent question) | Compares E6(R3) §2.8.10 with Helsinki ¶26 and attributes each position |
| *¿Cuál es la mejor receta de paella valenciana?* | Refused (max score 0.58 < 0.69), lists what the assistant covers |

## Evaluation

`scripts/03_evaluate.py` runs the hand-written bilingual golden set
(`data/eval/golden.jsonl`) and writes [`docs/evaluation.md`](docs/evaluation.md): retrieval
hit-rate@6 per language (document and section level), refusal accuracy on out-of-domain
questions, false-refusal rate on in-domain ones, and — with `--with-answers` — keyword
coverage of generated answers. Retrieval sanity check on 6 EN/ES pairs + 6 OOD queries:
in-domain max scores 0.75–0.88, out-of-domain 0.52–0.63 → the gate separates them cleanly.

## Repository layout

```
notebooks/compliance_assistant.ipynb   the graded notebook (with outputs)
app.py                                 Streamlit UI
src/compliance_assistant/
  config.py       settings, API key loading
  ingestion.py    PDF/HTML -> cleaned pages -> sectioned chunks with citation metadata
  vectorstore.py  embedding cache, manifest, Chroma rebuild (no API calls)
  retrieval.py    relevance scoring, calibrated gate, MMR, citations
  prompts.py      system prompts v1-v3, rewrite prompt, message assembly
  graph.py        the LangGraph StateGraph
  memory.py       checkpointer, thread config, history window
  agent.py        Assistant.ask() — the single entry point
  evaluation.py   golden-set harness
scripts/          00_download_sources · 01_build_kb · 02_sanity_retrieval · 03_evaluate · chat
tests/            offline pytest suite (fake LLM and embeddings)
data/kb/          sources.yaml, embeddings/ (cache), manifest.json, calibration.json
data/eval/        golden.jsonl (+ README)
docs/             sources, decisions, prompt iterations, evaluation, demo script
```

Development: `uv run pytest` · `uv run ruff check .` · `pre-commit install`.

## Limitations

Three documents (EU CTR, GVP and FDA regulations are out of scope by design); PDF tables
flatten into prose; the refusal threshold is corpus-specific; memory is in-process (a
restart forgets threads). This assistant gives regulatory information, **not legal or
medical advice**.

---

Academic project developed during the Master in Data Science & AI at
[Evolve Academy](https://evolveacademy.es).
