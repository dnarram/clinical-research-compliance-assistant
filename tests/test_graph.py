"""The agent graph, offline: routing, memory, thread isolation, query rewriting."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from compliance_assistant.agent import Assistant
from compliance_assistant.config import Settings
from compliance_assistant.memory import window_history
from compliance_assistant.prompts import REFUSAL_EN, REFUSAL_ES, looks_english


class RecordingLLM(BaseChatModel):
    """Returns canned answers and records every prompt it was given."""

    answers: list[str]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> ChatResult:
        self.calls.append(list(messages))
        text = self.answers.pop(0) if self.answers else "(no canned answer left)"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    @property
    def _llm_type(self) -> str:
        return "recording"


class ScoredStore:
    """Vector-store double whose score depends on the query (keyword hit = in-domain)."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.doc = Document(
            page_content="Fatal or life-threatening unexpected ADRs: 7 calendar days.",
            metadata={
                "doc_id": "ich_e2a",
                "short_cite": "ICH E2A",
                "section": "1",
                "page": 7,
                "url": "",
            },
        )

    def _score(self, query: str) -> float:
        return (
            0.9
            if any(w in query.lower() for w in ("adr", "report", "consent", "timeline"))
            else 0.3
        )

    def similarity_search_with_relevance_scores(self, query: str, k: int = 4):
        self.queries.append(query)
        return [(self.doc, self._score(query))]

    def max_marginal_relevance_search(
        self, query: str, k: int = 4, fetch_k: int = 20, lambda_mult: float = 0.5
    ):
        return [self.doc]


@pytest.fixture
def settings() -> Settings:
    return Settings(k=1, history_window=10, prompt_version="v3", score_threshold=0.6)


def make_assistant(
    settings: Settings, answers: list[str]
) -> tuple[Assistant, RecordingLLM, ScoredStore]:
    llm = RecordingLLM(answers=list(answers), calls=[])
    store = ScoredStore()
    return Assistant(llm, store, settings), llm, store


def test_in_domain_question_routes_to_generate_with_sources(settings: Settings) -> None:
    assistant, llm, _store = make_assistant(settings, ["Seven calendar days [1]."])
    ans = assistant.ask("What is the ADR reporting timeline?")
    assert ans.grounded and ans.text == "Seven calendar days [1]."
    assert [s.citation for s in ans.sources] == ["ICH E2A §1, p.7"]
    assert len(llm.calls) == 1, "first English turn: no rewrite call, one generate call"
    prompt = llm.calls[0]
    assert prompt[0].type == "system" and "GROUNDING" in prompt[0].content
    assert (
        "[1] ICH E2A §1, p.7" in prompt[-1].content
        and "Question: What is the ADR" in prompt[-1].content
    )
    assert prompt[-1].content.endswith("Reply in English.")


def test_out_of_domain_routes_to_refuse_without_llm(settings: Settings) -> None:
    assistant, llm, _ = make_assistant(settings, [])
    ans = assistant.ask("Best paella recipe?")
    assert not ans.grounded and ans.text == REFUSAL_EN and ans.sources == []
    assert llm.calls == []
    ans_es = assistant.ask("¿Cuál es la mejor receta de paella?")
    assert ans_es.text == REFUSAL_ES


def test_spanish_first_turn_is_rewritten_to_english_for_retrieval(settings: Settings) -> None:
    assistant, llm, store = make_assistant(
        settings, ["What is the ADR reporting timeline?", "Siete días [1]."]
    )
    ans = assistant.ask("¿Cuál es el plazo de notificación de una ADR?")
    assert ans.standalone_question == "What is the ADR reporting timeline?"
    assert store.queries[-1] == "What is the ADR reporting timeline?"
    assert ans.question.startswith("¿Cuál")
    assert "Question: ¿Cuál es el plazo" in llm.calls[-1][-1].content, (
        "answer prompt keeps the user's wording"
    )
    assert llm.calls[-1][-1].content.endswith("Responde en español.")


def test_memory_follow_up_uses_history_and_stays_within_window(settings: Settings) -> None:
    answers = [
        "Seven calendar days [1].",  # turn 1 generate
        "What is the timeline for other serious unexpected ADRs?",  # turn 2 rewrite
        "Fifteen calendar days [1].",  # turn 2 generate
        "Summarise the ADR reporting timelines discussed",  # turn 3 rewrite
        "7 days for fatal, 15 days for others [1].",  # turn 3 generate
    ]
    assistant, llm, _store = make_assistant(settings, answers)
    thread = assistant.new_thread()
    assistant.ask("What is the reporting timeline for a fatal unexpected ADR?", thread)
    a2 = assistant.ask("And for the other serious ones?", thread)
    assert a2.standalone_question == "What is the timeline for other serious unexpected ADRs?"
    rewrite_prompt = llm.calls[1][0].content
    assert "Seven calendar days" in rewrite_prompt, "rewrite sees the previous answer"
    a3 = assistant.ask("Summarise what you told me so far.", thread)
    assert a3.text.startswith("7 days for fatal")
    generate_prompt = llm.calls[-1]
    history_texts = [m.content for m in generate_prompt[1:-1]]
    # Q1, A1, Q2, A2 are in the window; the 5th message is the new question (in the last human message).
    assert history_texts == [
        "What is the reporting timeline for a fatal unexpected ADR?",
        "Seven calendar days [1].",
        "And for the other serious ones?",
        "Fifteen calendar days [1].",
    ]
    assert len(assistant.history(thread)) == 6


def test_window_caps_history_sent_to_the_model() -> None:
    msgs: list[BaseMessage] = []
    for i in range(8):
        msgs.append(HumanMessage(content=f"q{i}"))
        msgs.append(AIMessage(content=f"a{i}"))
    window = window_history(msgs, 10)
    assert len(window) == 10 and window[0].type == "human" and window[0].content == "q3"
    assert window_history(msgs, 3)[0].type == "human", "never starts on an assistant turn"
    assert window_history(msgs, 0) == []


def test_threads_are_isolated(settings: Settings) -> None:
    answers = ["A1 [1].", "A-other [1].", "rewrite for thread A", "A2 [1]."]
    assistant, llm, _ = make_assistant(settings, answers)
    a, b = assistant.new_thread(), assistant.new_thread()
    assistant.ask("ADR reporting timeline?", a)
    assistant.ask("Informed consent timeline?", b)
    assistant.ask("And the other ADRs?", a)
    assert len(assistant.history(a)) == 4 and len(assistant.history(b)) == 2
    rewrite_prompt = llm.calls[2][0].content
    assert "A1 [1]." in rewrite_prompt and "A-other" not in rewrite_prompt


def test_trace_lists_the_nodes_in_order(settings: Settings) -> None:
    assistant, _, _ = make_assistant(settings, ["ok [1]."])
    ans = assistant.ask("ADR timeline?", trace=True)
    assert [node for node, _ in ans.trace] == ["rewrite_query", "retrieve", "generate"]
    refused = assistant.ask("paella?", trace=True)
    assert [node for node, _ in refused.trace] == ["rewrite_query", "retrieve", "refuse"]


@pytest.mark.parametrize(
    ("text", "english"),
    [
        ("What is a SUSAR?", True),
        ("Summarise in two bullets what you told me so far.", True),
        ("And for the other serious ones?", True),
        ("Does the Declaration of Helsinki say the same about that situation?", True),
        ("¿Qué es un SUSAR?", False),
        ("Cual es el plazo para notificar", False),
        ("Resume en dos puntos lo que me has dicho hasta ahora.", False),
        ("Y para las demas reacciones graves, cual es el plazo?", False),
    ],
)
def test_language_heuristic(text: str, english: bool) -> None:
    assert looks_english(text) is english


def test_generic_fake_model_also_works(settings: Settings) -> None:
    """Guard: the graph only needs the BaseChatModel interface."""
    llm = GenericFakeChatModel(messages=iter([AIMessage(content="fine [1].")]))
    ans = Assistant(llm, ScoredStore(), settings).ask("consent rules?")
    assert ans.text == "fine [1]."


def test_invoke_with_retry_recovers_from_rate_limit_but_not_daily_quota() -> None:
    from compliance_assistant.graph import invoke_with_retry

    class Flaky(BaseChatModel):
        errors: list[str]

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            if self.errors:
                raise RuntimeError(self.errors.pop(0))
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

        @property
        def _llm_type(self) -> str:
            return "flaky"

    waits: list[float] = []
    llm = Flaky(errors=["429 RESOURCE_EXHAUSTED: Quota exceeded for metric requests per minute"])
    assert invoke_with_retry(llm, [HumanMessage(content="q")], sleep=waits.append).content == "ok"
    assert waits == [5.0]

    daily = Flaky(
        errors=["429 RESOURCE_EXHAUSTED: requests per day limit exceeded. Please retry in 22h"]
    )
    with pytest.raises(RuntimeError, match="per day"):
        invoke_with_retry(daily, [HumanMessage(content="q")], sleep=waits.append)
    assert waits == [5.0], "a daily quota error is not retried"


def test_offline_demo_replays_cached_answers(settings: Settings, tmp_path, monkeypatch) -> None:
    from dataclasses import replace

    offline_settings = replace(settings, project_root=tmp_path)
    assistant, llm, _ = make_assistant(offline_settings, ["Live [1]."])
    live = assistant.ask("ADR reporting timeline?")
    assistant.record_for_demo(live)
    assert assistant.settings.demo_cache_path.exists()

    monkeypatch.setenv("OFFLINE_DEMO", "1")
    replay = assistant.ask("ADR reporting timeline?")
    assert (
        replay.cached
        and replay.text == "Live [1]."
        and replay.sources[0].citation == "ICH E2A §1, p.7"
    )
    assert len(llm.calls) == 1, "the replay made no model call"
    assert len(assistant.history(replay.thread_id)) == 2, "the replayed turn is in the thread"

    monkeypatch.setenv("OFFLINE_DEMO", "0")
    assistant2, llm2, _ = make_assistant(offline_settings, ["Fresh [1]."])
    assert assistant2.ask("ADR reporting timeline?").text == "Fresh [1]." and len(llm2.calls) == 1


def test_dropped_connections_are_transient() -> None:
    from compliance_assistant.graph import _is_transient

    class RemoteProtocolError(Exception):
        pass

    assert _is_transient(RemoteProtocolError("Server disconnected without sending a response."))
    assert _is_transient(RuntimeError("503 UNAVAILABLE"))
    assert not _is_transient(RuntimeError("401 API key not valid"))
