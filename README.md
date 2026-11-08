# Clinical Research Compliance Assistant

An expert question-answering agent on **Good Clinical Practice (ICH E6(R3))**, **expedited
safety reporting (ICH E2A)** and the **WMA Declaration of Helsinki (2024)**, built with
Google Gemini, ChromaDB and LangGraph. It answers in English or Spanish, quotes the
regulatory text verbatim with section and page, remembers the conversation, and refuses
what its knowledge base does not cover.

Final project of the Generative AI module · Master in Data Science & AI · Evolve Academy ·
David Naranjo Ramírez

> **Live demo:** <https://clinical-research-compliance-assistant-eaksdytvqzbpuvthkakvrd.streamlit.app> · **Notebook:** [`notebooks/compliance_assistant.ipynb`](notebooks/compliance_assistant.ipynb)

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
| Retrieval | Standalone English query → relevance scores → **calibrated refusal gate** → MMR top-6 (shared between documents the question names) → **section-level context expansion** → numbered passages `[n]` cited `ICH E6(R3) §2.8.10, pp.24–26` / `Declaration of Helsinki (2024) ¶28` |
| Agent | Explicit LangGraph `StateGraph`: `rewrite_query → retrieve → route → generate \| refuse` |
| Memory | `InMemorySaver` checkpointer per `thread_id`; last 10 messages sent to the model |
| Languages | Answers in the user's language (EN/ES); regulatory wording quoted verbatim in English |
| Interfaces | Notebook chat cell, terminal REPL (`scripts/chat.py`), Streamlit app (`app.py`) |
| Evaluation | 25-item bilingual golden set (50 runs) → retrieval hit-rates, refusal accuracy, answer keyword coverage, honesty on not-indexed documents; baseline vs improved |

## Architecture

```
            ┌──────────────┐    ┌──────────┐    grounded?    ┌──────────┐
 question ─▶│ rewrite_query│───▶│ retrieve │──────yes───────▶│ generate │──▶ answer + sources
            │ (history →   │    │ gate,    │                 └──────────┘
            │  standalone  │    │ route,   │───────no───────▶┌──────────┐
            │  English q)  │    │ MMR,     │                 │  refuse  │──▶ "not in my KB; I cover…"
            │              │    │ expand   │                 └──────────┘
            └──────────────┘    └──────────┘
                  ▲  InMemorySaver checkpoint per thread_id (full history; 10-message window)
```

* **`rewrite_query`** resolves references to earlier turns ("*that* situation", "the same
  rule") and normalises the question to English, the corpus language. It skips the LLM on a
  first English turn.
* **`retrieve`** scores the top-k over the whole collection; if the best score is under the
  **calibrated threshold** (0.69, from in-domain vs out-of-domain query distributions in
  `data/kb/calibration.json`) the question is out of scope. Otherwise:
  * **document routing** — if the question names documents ("E6(R3)", "Helsinki", "E2A";
    aliases in `data/kb/sources.yaml`), the top-k is shared between them with a metadata
    filter, so "compare E6(R3) and Helsinki" gets passages from both;
  * **MMR** (`k=6, fetch_k=24, λ=0.6`) picks diverse chunks;
  * **context expansion** — each chunk is widened to its whole section when the section is
    ≤ 4,000 characters (a numbered requirement, a Helsinki paragraph, the 22 consent
    elements of E6(R3) §2.8.10), else to its neighbouring chunks, read from the collection
    with no API calls. A 500-character chunk had cut E2A's definition of *serious* in half.
  The gate always uses the unfiltered scores, so routing never changes what is refused.
* **`generate`** gets system prompt v4 + windowed history + numbered passages + the user's
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

The prompt in use (`SYSTEM_PROMPTS["v4"]` in [`src/compliance_assistant/prompts.py`](src/compliance_assistant/prompts.py)):

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
- A question may need several passages combined (for example a reporting chain:
  investigator to sponsor, then sponsor to regulators with its timelines). Build the
  answer step by step from the passages, citing each step.
- If the passages answer only part of the question, answer that part and say clearly
  which part they do not cover. Only when nothing in the passages is relevant, say that
  you could not find it in your knowledge base (in the user's language), state what the
  knowledge base covers, and stop. Never invent section numbers, timelines, definitions or
  responsibilities.
- When a passage contains a list (criteria, elements, responsibilities), give every item
  the passages contain. If the list visibly continues beyond the passages, say so instead
  of presenting it as complete.

SOURCES THAT DIFFER
- When passages from different documents (e.g. ICH E6(R3) vs the Declaration of
  Helsinki) address the same point differently, say so explicitly and attribute each
  position to its document. Do not merge them into one claim.

LANGUAGE
- Write the whole answer in the language of the user's question, including any statement
  that something is not covered (Spanish question -> Spanish answer).
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
| Graded insufficiency: answer the covered part and name the uncovered part; full "not in my knowledge base" (in the user's language) only when nothing is relevant | The rubric asks how the agent behaves without information; invented article numbers are the worst failure, but refusing a question whose steps are all in the passages is a failure too |
| Multi-step answers, each step cited | Reporting chains span E6(R3) (investigator → sponsor) and E2A (sponsor → regulator timelines) |
| Complete lists, or say the list continues | Criteria and elements are where partial answers mislead most |
| Sources that differ → attribute separately | E6(R3) and Helsinki overlap on consent and vulnerable participants but are not identical |
| Language policy | Corpus is English, users are Spanish-speaking; verbatim English quotes keep legal precision |
| Scope and tone | No legal/medical advice; stays on topic |
| Format | Direct answer first; chat-friendly |

**How it evolved** ([`docs/prompt_iterations.md`](docs/prompt_iterations.md), which separates
what was observed on the live model from structural reasoning): **v1**, the bare "answer
from the documents" prompt from class, answered correctly but with no citation markers, so
no sentence can be traced to a passage. **v2** added role, audience, scope and a refusal
rule (a design step, not evaluated on its own). **v3** added per-sentence citations, the
handling of documents that disagree, the language policy and the output format. The first
full golden-set run of v3 showed three failures — a multi-step question refused outright,
the Spanish version of that refusal written in English, and truncated lists presented as
complete — and **v4** addresses them together with context expansion and document routing
(results under *Evaluation*). One constraint lives in code rather than in the prompt: the
user message carries a deterministic `Reply in English.` / `Responde en español.` line,
because the prompt rule alone once let an English question be answered in Spanish.

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
OFFLINE_DEMO=1 uv run streamlit run app.py                 # replay the recorded demo script, no API calls
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

**Streamlit Cloud (how the public demo is deployed):** *New app* → repository
`dnarram/clinical-research-compliance-assistant`, branch `main`, main file `app.py`;
*Advanced settings* → Python 3.12 and, under *Secrets*, `GEMINI_API_KEY = "..."`. The app
installs `requirements.txt` (exported from `uv.lock`) and rebuilds the Chroma collection
from the committed embedding cache at first start — no embedding API calls.

**Free tier notes.** `gemini-embedding-2` allows **1,000 embedded texts per day** on the
free tier (a batch of 50 chunks counts as 50): the one-time corpus build uses ~800, which is
why the embedding cache is committed and query vectors are cached on disk
(`data/kb/query_cache.jsonl.gz`) — repeated questions cost no embedding calls. The build
batches 50 chunks per request, is resumable and backs off on 429. A second key from another
Google Cloud project (`GEMINI_API_KEY_BACKUP=` in `.env` / Streamlit secrets) is a second daily
budget: clients fail over to it automatically on a daily-quota error. Each chat turn costs 1–2 LLM calls
(`gemini-3.5-flash-lite`; the class default `gemini-2.5-flash-lite` is no longer served to
new keys — override with `LLM_MODEL=` in `.env` if yours differs).

## Example conversations

Executed outputs are in the notebook (sections 7–8) and in the recorded demo
(`data/demo/cached_answers.jsonl`). Abbreviated:

| Question | Behaviour |
|---|---|
| *What is the timeline for expedited reporting of a fatal unexpected ADR?* | "…as soon as possible but no later than 7 calendar days after first knowledge by the sponsor…", complete report within 8 additional days `[1]` — `ICH E2A §1, p.7` |
| *¿Y para las demás reacciones graves e inesperadas?* (same thread) | Searched as *"What is the timeline for expedited reporting of other serious and unexpected adverse drug reactions?"* → 15 calendar days, quoted verbatim, answered in Spanish |
| *¿Qué exigen ICH E6(R3) y la Declaración de Helsinki para incluir a participantes que no pueden dar su consentimiento?* | Both documents named → top-6 shared between them; contrasts E6(R3) Principle 2.1 (legally acceptable representative, best interest) with Helsinki ¶28 (legally authorized representative, minimal risk) and attributes each |
| *How does ICH E2A define a serious adverse event?* | All five criteria (death, life-threatening, hospitalisation, disability/incapacity, congenital anomaly) — before section expansion the answer stopped after two |
| *What does 21 CFR Part 50 say about informed consent?* | "I could not find information about 21 CFR Part 50 in my knowledge base…" — never invents FDA content |
| *¿Qué fármaco GLP-1 es mejor para perder peso?* | Refused by the retrieval gate (≈0.64 < 0.69) before any answer is generated |

## Evaluation

**Retrieval sanity check before the agent** (`scripts/02_sanity_retrieval.py`): 6 in-domain
EN/ES question pairs and 6 out-of-domain questions. In-domain maximum scores 0.75–0.88
(Spanish ≈0.04 lower, same passages), out-of-domain 0.52–0.63 → the refusal gate (0.69) is
the midpoint of that gap.

**Golden set** (`data/eval/golden.jsonl`, 25 items × EN/ES = 50 runs): 19 in-domain items
with the document and section that answer them (two need two documents), 4 out-of-domain,
2 about documents deliberately not indexed. Every reference is checked against the indexed
text by `tests/test_golden_consistency.py`; generated answers are saved next to the scores
(`data/eval/answers*.jsonl`).

| Metric (50 runs) | v3 baseline | **v4 + context expansion + document routing** |
|---|---|---|
| Answer keyword coverage | 0.815 | **0.974** |
| Document hit-rate@6 (EN / ES) | 1.0 / 1.0 | 1.0 / 1.0 |
| Section hit-rate@6 (EN / ES) | 0.947 / 1.0 | 0.947 / 0.947 |
| Out-of-domain refused (EN / ES) | 1.0 / 1.0 | 1.0 / 1.0 |
| In-domain wrongly refused | 0 | 0 |
| Honest "not in my knowledge base" on not-indexed documents | 1.0 | 1.0 |

Both rows use the same golden set and the same scoring (`docs/evaluation_baseline_v3.md`,
[`docs/evaluation.md`](docs/evaluation.md)).

**Correctness (LLM judge) and a held-out set.** Keyword coverage is a proxy, and the fixes
were developed while looking at the golden set, so two further checks
(`scripts/05_judge.py`, `data/eval/heldout.jsonl`):

| Judged correctness (correct 1 · partial 0.5 · incorrect 0) | v3 baseline | **v4 + fixes** |
|---|---|---|
| Golden set, 38 in-domain answers | 0.776 (23 / 13 / 2) | **0.947** (35 / 2 / 1) |
| **Held-out set**, 20 in-domain answers — written after v4 was frozen, run once | 0.950 (18 / 2 / 0) | **1.000** (20 / 0 / 0) |
| Held-out keyword coverage · retrieval · refusals · honesty | 0.925 · 1.0 · 1.0 · 1.0 | 1.0 · 1.0 · 1.0 · 1.0 |

The judge compares each answer with an expert reference answer. The intended judge,
`gemini-3.5-flash`, is limited to 20 requests a day on the free tier, so all four answer sets
were judged with `gemini-3.5-flash-lite` — the same model that writes the answers, which
invites self-preference. To check it, both judges scored the 38 v3 golden answers: 78.9 %
exact agreement, with `flash` stricter (0.697 vs 0.776). Read the absolute numbers as
optimistic by roughly that margin; the v3 → v4 comparison uses one judge throughout. The
held-out gain is smaller because its questions sit in single sections, where chunk truncation
rarely bit — no regression there. What changed and why is in
[`docs/decisions.md`](docs/decisions.md): reading every v3 answer showed lists cut by
chunking presented as complete (E2A *serious*: 2 of 5 criteria; E6(R3) consent elements:
4 of 22), a multi-step question refused outright, and that refusal written in English to a
Spanish question. Remaining weaknesses, reported rather than tuned away:

* **Multi-hop questions** — "from the investigator to the regulator, who reports to whom and
  when?" now gets a partial answer instead of a refusal, but one retrieval pass does not
  bring every hop (keyword coverage 0.67 EN / 0.33 ES on that item). The natural fix is
  query decomposition: one retrieval per hop.
* **Routing trade-off** — for the Spanish comparison question, the E6(R3)-filtered slots
  pick §2.8.1 and the glossary rather than Principle 2.1 (section hit 1.0 → 0.947 ES),
  although the agent's own answer, retrieved with the rewritten English question, cites
  Principle 2.1.
* **Keyword coverage is a proxy**, not a faithfulness score; an LLM-as-judge pass is the
  next measurement to add.

## Repository layout

```
notebooks/compliance_assistant.ipynb   the graded notebook (with outputs)
app.py                                 Streamlit UI
src/compliance_assistant/
  config.py       settings, API key loading
  ingestion.py    PDF/HTML -> cleaned pages -> sectioned chunks with citation metadata
  vectorstore.py  embedding cache, manifest, Chroma rebuild (no API calls)
  retrieval.py    relevance scoring, calibrated gate, MMR, citations
  prompts.py      system prompts v1-v4, rewrite prompt, message assembly
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
