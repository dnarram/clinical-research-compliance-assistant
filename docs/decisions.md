# Technical decisions (kept while building, not written afterwards)

Format: decision → why → what it cost / what it rules out.

## 2026-11-07 — Domain: clinical research compliance (ICH GCP, E2A, Helsinki)

Chosen over hospitality or consumer-law alternatives because it is the domain where the
author can judge answers (5 years in clinical-trial software support, ICH GCP E6(R2)
certified), the sources are public, English and section-numbered (precise citations), and
the recent E6(R3) (2025) is poorly known to the base model — so the value of RAG is visible.
Cost: the corpus is English while the demo audience asks in Spanish → an explicit language
policy was needed (see below).

## Read the brief from the PDF

Three copies of the assignment were supplied (.pages, .docx, .pdf). The PDF is the only
one readable with its layout intact (the rubric table). Content is identical across copies.

## Explicit LangGraph `StateGraph` instead of `create_agent` + retriever tool

The class "agentic RAG" pattern lets the LLM decide whether to call the retriever. The
brief requires the knowledge base to be used on every query, the free tier makes each
extra LLM call expensive (the ReAct loop needs ≥ 2), and a fixed topology is trivially
traceable (`stream_mode="updates"`). Routing is a deterministic `Literal["generate",
"refuse"]` on the retrieval score. Ruled out: the agent deciding to answer from memory.

## Versioned embedding cache as the source of truth (not the Chroma directory)

Chroma's on-disk format is tied to the chromadb version; a `jsonl.gz` of (id, text,
metadata, vector) is not. Rebuilding Chroma from the cache uses the native `add(embeddings=)`
path → zero API calls on a fresh clone, in Streamlit Cloud, in tests and in the demo.
`manifest.json` (file sha256 + embedding model + dim + chunking) makes the build idempotent;
chunk ids are deterministic so adds are upserts; stale ids are pruned when the cleaner
changes. Cost: 2.4 MB of versioned cache; 768 dimensions chosen (vs 3072 default) to keep it
small — acceptable on a 800-chunk corpus.

## Declaration of Helsinki from the WMA web page, not the PDF export

The WMA site generates its PDF from the page: paragraph numbers end up on their own line
("1\n.\nT\nhe World…"), every line is emitted twice, and ligatures are mangled
("Clari6cation", "su=cient"). The HTML carries the numbers as `<ol start="N">`, from which
`ingestion.load_html` rebuilds "N. text" lines. Section detection for Helsinki went from
0/70 chunks labelled to 67/68. Cost: a second loader (stdlib `html.parser`, no new
dependency) and a hash that changes if WMA edits the page (the download script reports it).

## Raw sources are not committed

ICH permits reproduction with attribution and the WMA text is public, but redistributing
publisher files in a public repo is not needed: `00_download_sources.py` fetches and
verifies them by sha256 and the embedding cache is enough to run everything. The notebook
downloads them on demand only for the pre-processing demonstration.

## Asymmetric embedding task types

Documents are embedded with `RETRIEVAL_DOCUMENT`, queries with `RETRIEVAL_QUERY`, as
separate embeddings instances. `gemini-embedding-2` accepts the hint (verified) although
its documentation says it does not apply it; the code is correct for `gemini-embedding-001`
too, where it does matter, so switching models does not silently change retrieval.

## Refusal threshold calibrated, not fixed

Gemini cosine relevance scores are compressed: in-domain maxima 0.75–0.88, out-of-domain
0.52–0.63 on six EN/ES query pairs plus six OOD queries. A fixed "0.5" would never refuse;
"0.8" would refuse half the Spanish questions. `02_sanity_retrieval.py --calibrate`
writes the midpoint of the gap (0.6885) to `calibration.json`; `Settings.score_threshold`
stays `None` unless deliberately overridden. Cost: the threshold must be re-calibrated if
the embedding model or the corpus changes (the file records the model).

## Language policy

Corpus and prompts in English. `rewrite_query` always produces an **English standalone
question** (resolving references to earlier turns and translating); retrieval runs on it.
The answer is written in the user's language, quoting regulatory wording verbatim in
English. Cross-lingual retrieval was measured before deciding: Spanish queries retrieve the
same passages with scores ~0.04 lower, so the rewrite is a safety net, not a crutch. One
LLM call is saved on first-turn English questions (cheap heuristic `looks_english`).

A deterministic `Reply in English.` / `Responde en español.` line is appended to the user
message because the system-prompt rule alone produced one Spanish answer to an English
question during testing. Hard constraints go in code; the prompt carries judgement.

## Memory window of 10 messages, applied at prompt time

The checkpointer keeps the whole thread; only the last 10 messages (5 turns), trimmed to
start on a user turn, are sent to the model. 10 rather than 6 because the demo script is
Q1 → referential Q2 → "summarise what you told me" (message 5), and 6 left no margin.
Retrieved passages are kept in graph state, not in `messages`, so the window counts turns.
`tests/test_graph.py` pins the window behaviour.

## Model: `gemini-3.5-flash-lite`

The class default `gemini-2.5-flash-lite` returns 404 for API keys created after the 3.x
rollout ("no longer available"). 3.x models ignore `temperature`, so it is only passed to
2.x models. Message content comes back as a list of blocks; `_text()` reads the `.text`
property so the code works with both generations.

## Golden set written by hand

`data/eval/golden.jsonl` carries the (document, section) that answers each question. That
ground truth is the author's domain contribution; the code ships the harness and a 3-item
template. Auto-generating questions from the corpus would only test that the retriever can
find the text the questions were generated from.

## Pre-commit secrets check without gitleaks

gitleaks needs a Go toolchain in the hook environment. Replaced with `detect-private-key`
plus a local hook that greps tracked files for the two Gemini key prefixes (`AIza…`,
`AQ.…`). `.env` is ignored; the notebook prints only the key length.

## 2026-11-08 — Free-tier embedding quota is per *text*, not per request

`gemini-embedding-2` on the free tier allows 1,000 embedded contents per day
(`embed_content_free_tier_requests`), and a batch of 50 chunks counts as 50. The 801-chunk
build plus three full notebook executions and the sanity/calibration runs exhausted the
day's quota (429 with "retry in 22h"). Consequences and fixes:

- The corpus is embedded **once**; the committed cache means nobody has to repeat it.
- Query embeddings are now cached on disk (`data/kb/query_cache.jsonl.gz`, versioned,
  keyed on query text + model) via `CachedQueryEmbeddings`. Repeated questions — the
  scripted demo, the golden set, the notebook — cost zero embedding requests after the
  first run, locally and on Streamlit Cloud.
- Demo-day rule: do not rebuild the knowledge base or re-execute the whole notebook before
  the presentation; a chat turn costs one embedding (if not cached) and 1–2 LLM calls.
- Fallback: a second API key from another Google account, switched via `.env` /
  Streamlit secrets.

## 2026-11-08 — Demo resilience: retry on per-minute limits, replay cache for the script

`graph.invoke_with_retry` retries a model call on transient errors (per-minute 429, 5xx)
with 5/10/20 s back-off and gives up immediately on a daily-quota error ("per day"), so
a live demo survives a rate blip without masking a real outage. `demo_cache.DemoCache`
stores the scripted demo conversation (`scripts/04_cache_demo_answers.py`); with
`OFFLINE_DEMO=1` an exact-match question is replayed without any API call and the UI
labels it "cached". Follow-ups are keyed on the previous question so a referential turn
replays in context. Honesty rule: the badge is always shown.

## 2026-11-08 — Backup API key = second daily quota

Free-tier quotas are per Google Cloud project (`…PerUserPerProjectPerModel`). A second key
created in a *new* project doubles the daily embedding budget. `load_api_keys()` returns
primary + `GEMINI_API_KEY_BACKUP`; `FailoverEmbeddings` / `FailoverChatModel` switch to the
next client only on a daily-quota error (per-minute limits are retried instead). Keys are
never logged; the build script prints only how many it has.

## 2026-11-08 — Evaluation-driven fixes: context expansion, document routing, prompt v4

The first full golden-set run (v3, 50 runs) had perfect retrieval metrics but answer keyword
coverage of 0.77. Reading every answer (they are now saved to `data/eval/answers*.jsonl`)
separated real failures from artefacts of the keyword list:

| Observation | Cause | Fix |
|---|---|---|
| E2A *serious* definition answered with 2 of its 5 criteria; E6(R3) consent elements answered with (a)–(d) of (a)–(v), both presented as complete | 500-character chunks cut lists; the rest sat in the next chunk | **Context expansion**: widen each chunk to its section if ≤ 4,000 chars, else to its neighbours (`retrieval.ContextIndex`). Measured: 393 of 399 section runs fit; §2.8.10 is 3,653 chars, so a 3,000 budget would still have cut it |
| "Compare E6(R3) and Helsinki on participants who cannot consent" got generic E6(R3) consent passages, not §2.8.13 (legally acceptable representative) | MMR over the whole collection; Helsinki ¶28–30 scored higher and took the slots | **Document routing**: when a question names documents (aliases in `sources.yaml`), share the top-k between them with a metadata filter. The refusal gate keeps using unfiltered scores, so the calibration is unaffected |
| "From the investigator to the regulator, who reports to whom and when?" refused outright; Spanish questions intermittently refused **in English** (that one in the first run, the 21 CFR / EU CTR ones in the re-run) | All-or-nothing insufficiency rule; the rule quoted the English sentence and the model copied it | **Prompt v4**: answer the covered part and name the uncovered part; build multi-step answers citing each step; state "not covered" in the user's language; give complete lists or say they continue |
| Correct Spanish answers scored as misses ("inmediatamente", "patrocinadores"); "IB" vs "Investigator's Brochure"; British "hospitalisation" vs my "hospitalization" | Keyword list written for English answers only | **Golden set**: variants with `a\|b`, whole-word matching, typographic quotes normalised. Made stricter where the expert answer requires it: all five *serious* criteria, a late consent element ("voluntary"), and multi-source items need a correct section **from each** document (`doc_id:section`) |

Both configurations were re-run with the **same** revised keywords (`--prompt-version v3
--no-expand --no-routing` vs defaults), so the comparison in `docs/evaluation.md` isolates
the pipeline change. Cost: prompts get longer (up to ~4,000 characters per passage).
