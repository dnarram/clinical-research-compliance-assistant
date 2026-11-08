# Demo script — 5–10 minutes

Slides: <https://claude.ai/artifact/FyZnhuoZ1R3cee1PtUsdgg> (7 slides; export to PPTX/PDF from its Share menu). **Offline copy:** [`slides/clinical-research-compliance-assistant-deck.pdf`](slides/clinical-research-compliance-assistant-deck.pdf) (16:9, regenerated with `uv run python docs/slides/build_pdf.py`, needs Google Chrome). Slide sources are kept in `docs/slides/`; the presenter-view notes (`<aside>`) are in Spanish and are not in the PDF — use `notas_orador_es.md`. The same notes, slide by slide, with timings and likely questions: [`notas_orador_es.md`](notas_orador_es.md).

Rehearse twice with a timer. Have **three windows** open before starting: the Streamlit
Cloud app (public URL), a local `uv run streamlit run app.py` as fallback, and the executed
notebook (`notebooks/compliance_assistant.ipynb`) scrolled to section 6.1 (trace).

Plan B, in order: local Streamlit → `OFFLINE_DEMO=1 uv run streamlit run app.py` (replays the
recorded script below with a "cached" badge; record it the day before with
`scripts/04_cache_demo_answers.py`) → notebook outputs (already executed) → `scripts/chat.py`.
Per-minute 429s are retried automatically (5/10/20 s); a *daily* quota error is not — switch
to the backup key or offline mode.

| Min | Beat | Say / do |
|---|---|---|
| 0:00 | **Problem** | "A CRA gets an SAE at 17:50 on a Friday. Is it a SUSAR? Who reports it, and by when? The answer is split across ICH E2A, E6(R3) and the Helsinki principles — and it has to be quoted exactly." Why me: 5 years in clinical-trial software support, GCP-certified. |
| 1:00 | **Stack + graph** (slide 2) | Gemini `3.5-flash-lite` + `gemini-embedding-2` · ChromaDB · LangGraph. Point at the graph: `rewrite_query → retrieve → route → generate / refuse`. Three decisions worth 20 s each: (1) versioned embedding cache → idempotent builds, zero API calls to rebuild; (2) relevance gate **calibrated** on in-domain vs out-of-domain queries (0.69), MMR for multi-document coverage; (3) checkpointer per `thread_id`, 10-message window, context kept out of history. |
| 2:00 | **Prompt v1 → v4** (slide 3) | v1 (class baseline): correct on the SUSAR question but no citation markers, no rule for missing information. v3 added `[n]` citations and the language policy; the golden-set run then showed truncated lists, a refused multi-step question and Spanish refusals in English → v4 (graded refusals, step-by-step answers, complete lists). "Hard constraints in code — the `Reply in English/Responde en español` line — judgement in the prompt." Do not claim v1 invented citations: that was never observed. |
| 3:00 | **Live demo** (Streamlit) | Q1 *What is the timeline for expedited reporting of a fatal unexpected ADR?* → 7 days + 8 days, `ICH E2A §1, p.7`. Open the sources panel. |
| 4:00 | | Q2 *¿Y para las demás reacciones graves e inesperadas?* → rewritten to a standalone English question (shown as "Searched as:"), answered in Spanish: 15 days. **Memory + language policy in one turn.** |
| 5:00 | | Q3 *¿Qué exigen ICH E6(R3) y la Declaración de Helsinki para incluir a participantes que no pueden dar su consentimiento?* → both documents named, so retrieval shares the top-6 between them (document routing); contrasts E6(R3) Principle 2.1 / §2.8.13 with Helsinki ¶28 and attributes each. **Multi-source.** |
| 6:00 | | Q4 *¿Qué fármaco GLP-1 es mejor para perder peso?* → refused, best score ≈0.64 < 0.69 (the rewrite adds "in clinical research", which narrows the margin — if it ever answers, say so: the gate is calibrated on 12 queries and this is its closest call), lists what it covers. "The answering model never saw this question." |
| 6:45 | **Trace** (notebook 6.1) | Show the node-by-node `stream_mode="updates"` output for one question: rewrite → retrieve (score, threshold, grounded) → generate. |
| 7:30 | **Evaluation** (slide 4) | Golden set, bilingual: doc hit-rate@6, section hit-rate, refusal accuracy, false-refusal rate. Retrieval sanity: in-domain 0.75–0.88 vs OOD 0.52–0.63. |
| 8:30 | **Limitations / next** (slide 5) | 3 documents by design; tables flatten; threshold is corpus-specific; memory in-process. Next: query decomposition for multi-hop questions, GVP VI + EU CTR, a faithfulness judge against the retrieved passages (the current judge checks correctness against expert references), hybrid BM25, `guard_input` node. |
| 9:00 | Questions | |

## Likely questions

- *Why not `create_agent` with a retriever tool?* The brief requires the KB on every query;
  a fixed graph is 1–2 LLM calls instead of ≥ 2 per ReAct loop; it is trivially traceable.
- *How do you know the threshold is right?* Read off the data (`02_sanity_retrieval.py
  --calibrate`): the gap between the lowest in-domain and the highest out-of-domain max
  score. It is recorded with the embedding model; change the model, recalibrate.
- *What happens with a question about a regulation you don't index (21 CFR)?* Retrieval
  still finds consent passages (score 0.77), the model answers "not in my knowledge base;
  it covers …" — because the prompt forbids outside knowledge. Shown in notebook §8.
- *Does Spanish retrieval work as well?* Same passages, scores ~0.04 lower; the rewrite to
  English is the safety net. Measured in §4 and in the golden set per language.
- *Cost?* Embedding the corpus: 17 requests, once. Each turn: 1–2 LLM calls.
