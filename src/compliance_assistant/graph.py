"""The LangGraph agent: rewrite_query -> retrieve -> (route) -> generate | refuse.

Why an explicit graph rather than `create_agent` with a retriever tool: the brief requires
the knowledge base to be used on *every* query, the free tier makes every extra LLM call
expensive, and a fixed topology is easy to trace in the notebook. The LLM never decides
whether to retrieve; it only rewrites (when there is history) and answers.

State keeps the retrieved context *outside* `messages`, so the persisted conversation
stays small and the memory window counts turns, not passages.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.vectorstores import VectorStore
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from compliance_assistant.config import Settings
from compliance_assistant.memory import make_checkpointer, window_history
from compliance_assistant.prompts import (
    REFUSAL_EN,
    REFUSAL_ES,
    REWRITE_PROMPT,
    SYSTEM_PROMPTS,
    build_messages,
    format_history,
    looks_english,
)
from compliance_assistant.retrieval import format_context, retrieve

log = logging.getLogger(__name__)


class AgentState(MessagesState):
    """`messages` (with the add_messages reducer) comes from MessagesState."""

    question: str
    standalone_question: str
    language: str  # "en" | "es" — decided once per turn, drives the answer language
    context: str
    sources: list[dict[str, Any]]
    grounded: bool
    max_score: float


def _text(message: BaseMessage) -> str:
    """Plain text of a message; Gemini 3.x returns content as a list of blocks."""
    # langchain-core 1.x: `.text` is a property (a str that is also callable for backward
    # compatibility — do not call it, that triggers a deprecation warning).
    text = getattr(message, "text", None)
    if isinstance(text, str) and text:
        return str(text)
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def build_graph(
    llm: BaseChatModel,
    vectorstore: VectorStore,
    settings: Settings,
    checkpointer: BaseCheckpointSaver | None = None,
    threshold: float | None = None,
) -> CompiledStateGraph:
    """Compile the agent. `llm` and `vectorstore` are injected so tests run offline."""
    system_prompt = SYSTEM_PROMPTS[settings.prompt_version]
    gate = threshold if threshold is not None else settings.resolved_threshold()

    def rewrite_query(state: AgentState) -> dict[str, Any]:
        messages = state["messages"]
        question = _text(messages[-1])
        language = "en" if looks_english(question) else "es"
        history = window_history(messages[:-1], settings.history_window)
        if not history and language == "en":
            log.info("[rewrite_query] first turn, English: used as-is")
            return {"question": question, "standalone_question": question, "language": language}
        prompt = REWRITE_PROMPT.format(history=format_history(history), question=question)
        standalone = (
            _text(llm.invoke([HumanMessage(content=prompt)])).strip().strip('"') or question
        )
        log.info("[rewrite_query] (%s) %r -> %r", language, question, standalone)
        return {"question": question, "standalone_question": standalone, "language": language}

    def retrieve_node(state: AgentState) -> dict[str, Any]:
        result = retrieve(vectorstore, state["standalone_question"], settings, threshold=gate)
        log.info(
            "[retrieve] max_score=%.3f threshold=%s grounded=%s docs=%d",
            result.max_score,
            f"{gate:.3f}" if gate is not None else "off",
            result.grounded,
            len(result.docs),
        )
        return {
            "context": format_context(result.sources),
            "sources": [asdict(s) for s in result.sources],
            "grounded": result.grounded,
            "max_score": result.max_score,
        }

    def route_after_retrieve(state: AgentState) -> Literal["generate", "refuse"]:
        return "generate" if state["grounded"] else "refuse"

    def generate(state: AgentState) -> dict[str, Any]:
        history = window_history(state["messages"][:-1], settings.history_window)
        prompt = build_messages(
            system_prompt,
            history,
            state["context"],
            state["question"],
            language=state.get("language", "en"),
        )
        answer = _text(llm.invoke(prompt))
        log.info("[generate] %d chars, %d sources", len(answer), len(state["sources"]))
        return {"messages": [AIMessage(content=answer)]}

    def refuse(state: AgentState) -> dict[str, Any]:
        text = REFUSAL_EN if state.get("language", "en") == "en" else REFUSAL_ES
        log.info("[refuse] out of scope (max_score=%.3f)", state["max_score"])
        return {"messages": [AIMessage(content=text)]}

    graph = StateGraph(AgentState)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate)
    graph.add_node("refuse", refuse)
    graph.add_edge(START, "rewrite_query")
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_conditional_edges(
        "retrieve", route_after_retrieve, {"generate": "generate", "refuse": "refuse"}
    )
    graph.add_edge("generate", END)
    graph.add_edge("refuse", END)
    return graph.compile(checkpointer=checkpointer or make_checkpointer())
