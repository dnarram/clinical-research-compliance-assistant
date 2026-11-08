"""The one entry point used by the notebook, the Streamlit app, the evaluation and the
terminal chat: `Assistant.ask(question, thread_id)`."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.vectorstores import VectorStore
from langgraph.checkpoint.base import BaseCheckpointSaver

from compliance_assistant.config import Settings, load_api_key, load_settings
from compliance_assistant.demo_cache import CachedAnswer, DemoCache
from compliance_assistant.graph import _text, build_graph
from compliance_assistant.memory import new_thread_config
from compliance_assistant.retrieval import Source

log = logging.getLogger(__name__)


def make_llm(settings: Settings, api_key: str) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, Any] = {"model": settings.llm_model, "google_api_key": api_key}
    # Gemini 3.x models use fixed sampling defaults and warn if temperature is set.
    if not settings.llm_model.replace("models/", "").startswith("gemini-3"):
        kwargs["temperature"] = settings.llm_temperature
    return ChatGoogleGenerativeAI(**kwargs)


@dataclass
class Answer:
    text: str
    sources: list[Source]
    grounded: bool
    max_score: float
    question: str
    standalone_question: str
    thread_id: str
    trace: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    cached: bool = False

    def __str__(self) -> str:
        return self.text


class Assistant:
    def __init__(
        self,
        llm: BaseChatModel,
        vectorstore: VectorStore,
        settings: Settings | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        threshold: float | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.threshold = threshold if threshold is not None else self.settings.resolved_threshold()
        self.vectorstore = vectorstore
        self.demo_cache = DemoCache(self.settings.demo_cache_path)
        self.graph = build_graph(
            llm, vectorstore, self.settings, checkpointer, threshold=self.threshold
        )

    @classmethod
    def from_settings(cls, settings: Settings | None = None, **kwargs: Any) -> Assistant:
        """Wire real Gemini clients and the persisted Chroma collection."""
        from compliance_assistant.vectorstore import build_or_load, get_query_embeddings

        settings = settings or load_settings()
        api_key = load_api_key()
        store = build_or_load(settings, get_query_embeddings(settings, api_key))
        return cls(make_llm(settings, api_key), store, settings, **kwargs)

    # --- conversation -----------------------------------------------------------------

    @staticmethod
    def new_thread() -> str:
        return new_thread_config()["configurable"]["thread_id"]

    def ask(self, question: str, thread_id: str | None = None, trace: bool = False) -> Answer:
        thread_id = thread_id or self.new_thread()
        config = new_thread_config(thread_id)
        if DemoCache.enabled():
            previous = self.history(thread_id)
            prev_q = _text(previous[-2]) if len(previous) >= 2 else ""
            hit = self.demo_cache.get(question, prev_q)
            if hit is not None:
                # Record the turn so later follow-ups in this thread still see it.
                self.graph.update_state(
                    config,
                    {"messages": [HumanMessage(content=question), AIMessage(content=hit.text)]},
                )
                return Answer(
                    text=hit.text,
                    sources=[Source(**s) for s in hit.sources],
                    grounded=hit.grounded,
                    max_score=hit.max_score,
                    question=question,
                    standalone_question=hit.standalone_question,
                    thread_id=thread_id,
                    cached=True,
                )
        steps: list[tuple[str, dict[str, Any]]] = []
        inputs = {"messages": [HumanMessage(content=question)]}
        if trace:
            for update in self.graph.stream(inputs, config=config, stream_mode="updates"):
                for node, delta in update.items():
                    steps.append((node, delta))
        else:
            self.graph.invoke(inputs, config=config)
        state = self.graph.get_state(config).values
        return Answer(
            text=_text(state["messages"][-1]),
            sources=[Source(**s) for s in state.get("sources", [])],
            grounded=bool(state.get("grounded", False)),
            max_score=float(state.get("max_score", 0.0)),
            question=state.get("question", question),
            standalone_question=state.get("standalone_question", question),
            thread_id=thread_id,
            trace=steps,
        )

    def stream_updates(self, question: str, thread_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
        """Node-by-node updates, for showing the graph at work in the notebook."""
        config = new_thread_config(thread_id)
        for update in self.graph.stream(
            {"messages": [HumanMessage(content=question)]}, config=config, stream_mode="updates"
        ):
            yield from update.items()

    def history(self, thread_id: str) -> list[BaseMessage]:
        snapshot = self.graph.get_state(new_thread_config(thread_id))
        return list(snapshot.values.get("messages", [])) if snapshot and snapshot.values else []

    def record_for_demo(self, answer: Answer, previous_question: str = "") -> None:
        """Store an answer for OFFLINE_DEMO replay (used by scripts/04_cache_demo_answers.py)."""
        self.demo_cache.put(
            CachedAnswer(
                question=answer.question,
                text=answer.text,
                sources=[s.__dict__ for s in answer.sources],
                grounded=answer.grounded,
                max_score=answer.max_score,
                standalone_question=answer.standalone_question,
                thread_key=previous_question.strip(),
            )
        )
