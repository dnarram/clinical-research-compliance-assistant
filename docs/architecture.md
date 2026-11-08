# Architecture

![agent graph](img/graph.png)

(`img/graph.mmd` holds the Mermaid source rendered by `graph.get_graph().draw_mermaid()`.)

## Components

| Layer | Module | Role |
|---|---|---|
| Sources | `data/kb/sources.yaml`, `scripts/00_download_sources.py` | Inventory with URL + SHA-256; raw files fetched on demand, never committed |
| Ingestion | `ingestion.py` | PDF (pypdf) / HTML (stdlib parser) → cleaned pages → section-aware recursive chunks (500/50) with `doc_id`, `section`, `page` metadata; deterministic chunk ids |
| Embeddings + store | `vectorstore.py` | `EmbeddingCache` (jsonl.gz per doc, resumable, 429 back-off) · `manifest.json` (hash/model/dim/chunking) · Chroma rebuilt from cache via native `add(embeddings=…)` |
| Retrieval | `retrieval.py` | `similarity_search_with_relevance_scores` → calibrated gate → `max_marginal_relevance_search` → numbered `Source`s and citation strings |
| Prompts | `prompts.py` | `SYSTEM_PROMPTS` v1–v3, `REWRITE_PROMPT`, `build_messages` (adds the answer-language line), `looks_english` |
| Agent | `graph.py`, `memory.py`, `agent.py` | LangGraph `StateGraph` + `InMemorySaver`; `Assistant.ask()` facade used by notebook, app, REPL and evaluation |
| Evaluation | `evaluation.py`, `scripts/03_evaluate.py` | Bilingual golden set → hit-rates, refusal accuracy, keyword coverage |
| UIs | `notebooks/compliance_assistant.ipynb`, `app.py`, `scripts/chat.py` | Same `Assistant`, three surfaces |

## Graph state

```python
class AgentState(MessagesState):  # messages: Annotated[list[AnyMessage], add_messages]
    question: str  # the user's wording (answered in this language)
    standalone_question: str  # English, self-contained; what gets embedded
    language: str  # "en" | "es", decided once per turn
    context: str  # numbered passages "[n] cite\ntext" — NOT in messages
    sources: list[dict]  # Source records for the UI
    grounded: bool  # max_score >= calibrated threshold
    max_score: float
```

Only `messages` is accumulated across turns (the `add_messages` reducer); every other key
is overwritten each turn. Keeping `context` out of `messages` means the checkpointed
thread holds just the dialogue, and the 10-message window counts turns.

## Node contracts

| Node | Reads | Writes | LLM calls |
|---|---|---|---|
| `rewrite_query` | last message, windowed history | `question`, `standalone_question`, `language` | 0 on a first English turn, else 1 |
| `retrieve` | `standalone_question` | `context`, `sources`, `grounded`, `max_score` | 0 (1 query embedding) |
| `route_after_retrieve` | `grounded` | — | 0 → `"generate"` or `"refuse"` |
| `generate` | system prompt, windowed history, `context`, `question`, `language` | `messages` (+AIMessage) | 1 |
| `refuse` | `language`, `max_score` | `messages` (+AIMessage, templated) | 0 |

Per turn: 1 query embedding + 1–2 LLM calls.

## Memory

`InMemorySaver` checkpoints the full state after every super-step under
`config={"configurable": {"thread_id": ...}}`. The notebook creates thread ids explicitly;
the Streamlit app stores one per browser session (`st.session_state`) and rotates it on
"New conversation". `memory.window_history(messages, 10)` trims to the last 10 messages
starting on a human turn before the prompt is built.

## Retrieval gate calibration

`scripts/02_sanity_retrieval.py --calibrate` embeds six EN/ES in-domain query pairs and
six out-of-domain queries, records the max relevance score of each, and writes the midpoint
of the gap between the lowest in-domain and the highest out-of-domain score to
`data/kb/calibration.json` (0.6885 with `gemini-embedding-2`, 768 d). `Settings.score_threshold`
is `None` by default so the calibrated value is used; `SCORE_THRESHOLD=` in `.env` overrides.

## Data flow for a build

```
sources.yaml ─▶ 00_download_sources.py ─▶ data/kb/raw/*.pdf|html  (sha256 verified, git-ignored)
                                               │ ingest()
                                               ▼
                             chunks (id = doc:p{page}:c{idx}:{sha1[:8]})
                                               │ embed_missing()  (only ids absent from cache)
                                               ▼
                 data/kb/embeddings/<doc>.jsonl.gz  +  manifest.json   (VERSIONED)
                                               │ rebuild_chroma()  (native add, no API)
                                               ▼
                                     data/chroma/   (derived, git-ignored)
```
