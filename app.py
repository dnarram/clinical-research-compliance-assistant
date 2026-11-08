"""Streamlit chat UI for the Clinical Research Compliance Assistant.

Thin wrapper over `compliance_assistant.agent.Assistant`: the same graph, prompts and
knowledge base as the notebook. Run locally with `uv run streamlit run app.py`; on
Streamlit Cloud the key comes from the app's Secrets (GEMINI_API_KEY).
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

import streamlit as st

# --- environment -------------------------------------------------------------------------
# Streamlit Cloud: secrets -> environment, before the settings module reads it.
for _name in ("GEMINI_API_KEY", "GEMINI_API_KEY_BACKUP"):
    if _name not in os.environ:
        with contextlib.suppress(KeyError, FileNotFoundError):
            os.environ[_name] = st.secrets[_name]

# chromadb needs sqlite >= 3.35; some Linux images ship an older one. pysqlite3-binary is
# only installed on Linux (see pyproject) and only used when needed.
try:
    import sqlite3

    if tuple(int(x) for x in sqlite3.sqlite_version.split(".")[:2]) < (3, 35):
        __import__("pysqlite3")
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from compliance_assistant.agent import Assistant
from compliance_assistant.config import MissingApiKeyError, load_settings
from compliance_assistant.ingestion import load_sources

st.set_page_config(
    page_title="Clinical Research Compliance Assistant", page_icon="🧪", layout="wide"
)


@st.cache_resource(show_spinner="Loading the knowledge base…")
def get_assistant() -> Assistant:
    # Rebuilds Chroma from the versioned embedding cache if needed: no embedding API calls.
    return Assistant.from_settings()


settings = load_settings()

# --- sidebar --------------------------------------------------------------------------------
with st.sidebar:
    st.title("🧪 Compliance Assistant")
    st.caption(
        "Expert Q&A on **ICH E6(R3)** Good Clinical Practice, **ICH E2A** expedited safety "
        "reporting and the **WMA Declaration of Helsinki (2024)**. Ask in English or Spanish."
    )
    st.markdown("**Knowledge base**")
    for src in load_sources(settings):
        st.markdown(f"- [{src.short_cite}]({src.url})" if src.url else f"- {src.short_cite}")
    st.markdown("**Agent**")
    st.markdown(
        f"- LLM: `{settings.llm_model}`\n"
        f"- Embeddings: `{settings.embedding_model}` ({settings.embedding_dim} d)\n"
        f"- Retrieval: top-{settings.k} MMR, calibrated refusal gate\n"
        f"- Memory: last {settings.history_window} messages per conversation"
    )
    if st.button("🗨️ New conversation", use_container_width=True):
        st.session_state.thread_id = Assistant.new_thread()
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.caption(
        "Regulatory information, **not legal or medical advice**. "
        "[Source code](https://github.com/dnarram/clinical-research-compliance-assistant) · "
        "Master in Data Science & AI, Evolve Academy — David Naranjo Ramírez."
    )

# --- state ----------------------------------------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = Assistant.new_thread()
if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    assistant = get_assistant()
except MissingApiKeyError as exc:
    st.error(str(exc))
    st.stop()

# --- conversation -----------------------------------------------------------------------------
st.markdown("#### Ask about GCP, safety reporting timelines, informed consent, essential records…")
if not st.session_state.messages:
    examples = [
        "What is the timeline for expedited reporting of a fatal unexpected ADR?",
        "¿Qué debe contener el consentimiento informado según ICH E6(R3)?",
        "Compare ICH E6(R3) and the Declaration of Helsinki on participants who cannot consent.",
    ]
    st.caption("Try: " + " · ".join(f"*{e}*" for e in examples))


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)} passages)"):
        for s in sources:
            score = f" · relevance {s['score']:.2f}" if s.get("score") else ""
            st.markdown(f"**[{s['n']}] {s['citation']}**{score}")
            st.caption(s["text"][:500] + ("…" if len(s["text"]) > 500 else ""))


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            render_sources(m.get("sources", []))

if question := st.chat_input("Your question (EN / ES)"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Searching the guidelines…"):
            try:
                answer = assistant.ask(question, st.session_state.thread_id)
            except Exception as exc:
                msg = str(exc)
                hint = (
                    " (free-tier rate limit — wait a minute and retry)"
                    if "429" in msg or "quota" in msg.lower()
                    else ""
                )
                st.error(f"The model call failed{hint}: {msg[:300]}")
                st.stop()
        st.markdown(answer.text)
        sources = [
            {"n": s.n, "citation": s.citation, "text": s.text, "score": s.score}
            for s in answer.sources
        ]
        render_sources(sources)
        if answer.cached:
            st.caption("Cached answer (offline demo mode).")
        if not answer.grounded:
            st.caption(
                f"No passage scored above the refusal threshold (best {answer.max_score:.2f} < {assistant.threshold})."
            )
        elif answer.standalone_question != answer.question:
            st.caption(f"Searched as: *{answer.standalone_question}*")
    st.session_state.messages.append(
        {"role": "assistant", "content": answer.text, "sources": sources}
    )
