"""LLM judge: prompt assembly and robust parsing, offline."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, ValidationError

from compliance_assistant.judge import Verdict, judge_answer, parse_verdict


class Canned(BaseChatModel):
    replies: list[str]
    prompts: list[str] = Field(default_factory=list)

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> ChatResult:
        self.prompts.append(str(messages[-1].content))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.replies.pop(0)))]
        )

    @property
    def _llm_type(self) -> str:
        return "canned"


def test_parse_verdict_accepts_fenced_json() -> None:
    v = parse_verdict(
        '```json\n{"verdict": "partially_correct", "missing": ["15 days"], "errors": [], "language_ok": true, "rationale": "x"}\n```'
    )
    assert v.verdict == "partially_correct" and v.score == 0.5 and v.missing == ["15 days"]


def test_parse_verdict_rejects_unknown_labels() -> None:
    with pytest.raises(ValidationError):
        parse_verdict('{"verdict": "mostly right"}')


def test_judge_retries_once_on_garbage_and_fills_the_prompt() -> None:
    llm = Canned(replies=["sorry, I cannot", '{"verdict": "correct", "language_ok": false}'])
    v = judge_answer(llm, "¿Plazo?", "15 calendar days (E2A).", "Quince días [1].", "es")
    assert isinstance(v, Verdict) and v.verdict == "correct" and v.language_ok is False
    assert len(llm.prompts) == 2
    assert "written in Spanish" in llm.prompts[0] and "15 calendar days (E2A)." in llm.prompts[0]


def test_judge_gives_up_after_two_bad_outputs() -> None:
    with pytest.raises(ValueError):
        judge_answer(Canned(replies=["no", "still no"]), "q", "ref", "ans", "en")


def test_agreement_between_judges() -> None:
    from compliance_assistant.judge import agreement

    a = [
        {"id": "x", "lang": "en", "verdict": "correct"},
        {"id": "y", "lang": "en", "verdict": "partially_correct"},
    ]
    b = [
        {"id": "x", "lang": "en", "verdict": "correct"},
        {"id": "y", "lang": "en", "verdict": "incorrect"},
        {"id": "z", "lang": "es", "verdict": "correct"},
    ]
    stats = agreement(a, b)
    assert (
        stats["n"] == 2 and stats["exact_agreement"] == 0.5 and stats["mean_abs_score_diff"] == 0.25
    )
    assert stats["confusion"] == {"correct -> correct": 1, "partially_correct -> incorrect": 1}
    assert agreement(a, [])["n"] == 0
