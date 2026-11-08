# Demo script — 5–10 minutes

Slides: <https://claude.ai/artifact/FyZnhuoZ1R3cee1PtUsdgg> (7 slides; export to PPTX/PDF from its Share menu). Slide sources are kept in `docs/slides/`.

Rehearse twice with a timer. Have **three windows** open before starting: the Streamlit
Cloud app (public URL), a local `uv run streamlit run app.py` as fallback, and the executed
notebook (`notebooks/compliance_assistant.ipynb`) scrolled to section 6.1 (trace).

Plan B, in order: local Streamlit → notebook outputs (already executed, no API needed to
*show*) → `uv run scripts/chat.py`. If the API returns 429, wait 60 s; the free tier resets
per minute.

| Min | Beat | Say / do |
|---|---|---|
| 0:00 | **Problem** | "A CRA gets an SAE at 17:50 on a Friday. Is it a SUSAR? Who reports it, and by when? The answer is split across ICH E2A, E6(R3) and the Helsinki principles — and it has to be quoted exactly." Why me: 5 years in clinical-trial software support, GCP-certified. |
| 1:00 | **Stack + graph** (slide 2) | Gemini `3.5-flash-lite` + `gemini-embedding-2` · ChromaDB · LangGraph. Point at the graph: `rewrite_query → retrieve → route → generate / refuse`. Three decisions worth 20 s each: (1) versioned embedding cache → idempotent builds, zero API calls to rebuild; (2) relevance gate **calibrated** on in-domain vs out-of-domain queries (0.69), MMR for multi-document coverage; (3) checkpointer per `thread_id`, 10-message window, context kept out of history. |
| 2:00 | **Prompt v1 → v3** (slide 3) | One failing v1 answer (no attribution, answered 21 CFR from memory) next to v3 (per-sentence `[n]` citations, verbatim quotes, refusal). "Hard constraints in code — the `Reply in English/Responde en español` line — judgement in the prompt." |
| 3:00 | **Live demo** (Streamlit) | Q1 *What is the timeline for expedited reporting of a fatal unexpected ADR?* → 7 days + 8 days, `ICH E2A §1, p.7`. Open the sources panel. |
| 4:00 | | Q2 *¿Y para las demás reacciones graves e inesperadas?* → rewritten to a standalone English question (shown as "Searched as:"), answered in Spanish: 15 days. **Memory + language policy in one turn.** |
| 5:00 | | Q3 *¿Dice lo mismo la Declaración de Helsinki sobre los participantes que no pueden consentir?* → contrasts E6(R3) §2.8.13 with Helsinki ¶28 and attributes each. **Multi-source.** |
| 6:00 | | Q4 *¿Qué fármaco GLP-1 es mejor para perder peso?* → refused, best score 0.63 < 0.69, lists what it covers. "The model never saw this question." |
| 6:45 | **Trace** (notebook 6.1) | Show the node-by-node `stream_mode="updates"` output for one question: rewrite → retrieve (score, threshold, grounded) → generate. |
| 7:30 | **Evaluation** (slide 4) | Golden set, bilingual: doc hit-rate@6, section hit-rate, refusal accuracy, false-refusal rate. Retrieval sanity: in-domain 0.75–0.88 vs OOD 0.52–0.63. |
| 8:30 | **Limitations / next** (slide 5) | 3 documents by design; tables flatten; threshold is corpus-specific; memory in-process. Next: GVP VI + EU CTR, hybrid BM25, LLM-as-judge, `guard_input` node. |
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
