"""LLM-as-judge: correctness of an answer against the expert reference of a golden item.

Keyword coverage (evaluation.py) only checks that expected phrases appear. The judge reads
the answer and the expert reference and returns a structured verdict:

* ``correct`` — every point the question asks for is present and nothing contradicts the
  reference;
* ``partially_correct`` — nothing wrong, but something the question asks for is missing;
* ``incorrect`` — a contradiction (wrong timeline, definition, responsibility or document),
  or a refusal although the reference shows the answer exists.

The judge is a different, larger model (`gemini-3.5-flash`) than the one that writes the
answers (`gemini-3.5-flash-lite`), to limit self-preference. It never sees the retrieved
passages: it checks correctness against the expert, not faithfulness to the context.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, ValidationError

from compliance_assistant.graph import _text, invoke_with_retry

JUDGE_MODEL = "gemini-3.5-flash"
SCORES = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}
LANGUAGE_NAMES = {"en": "English", "es": "Spanish"}


class Verdict(BaseModel):
    verdict: Literal["correct", "partially_correct", "incorrect"]
    missing: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    language_ok: bool = True
    rationale: str = ""

    @property
    def score(self) -> float:
        return SCORES[self.verdict]


JUDGE_PROMPT = """\
You audit answers given by a clinical-research compliance assistant (ICH E6(R3), ICH E2A,
Declaration of Helsinki). Compare the ANSWER with the EXPERT REFERENCE for the QUESTION.

Rules:
- Judge only what the QUESTION asks for. The reference may contain more detail than the
  question needs; missing detail the question did not ask for is not a fault.
- "correct": every point the question asks for is present and nothing contradicts the
  reference.
- "partially_correct": nothing contradicts the reference, but at least one point the
  question asks for is missing, incomplete, or a list is cut short without saying so.
- "incorrect": the answer contradicts the reference (wrong timeline, definition,
  responsibility or document), invents regulatory content, or says the information is not
  available although the reference shows it is.
- Extra correct detail is not an error. Do not check citation numbers like [1]. Section
  numbers matter only if they contradict the reference.
- "language_ok" is true when the answer is written in {language}; English quotations of
  regulatory text inside a Spanish answer are expected and fine.

QUESTION:
{question}

EXPERT REFERENCE:
{reference}

ANSWER:
{answer}

Reply with JSON only, no prose and no code fences:
{{"verdict": "correct" | "partially_correct" | "incorrect", "missing": ["..."], "errors": ["..."], "language_ok": true | false, "rationale": "one or two sentences"}}"""


def parse_verdict(text: str) -> Verdict:
    """Accept bare JSON or JSON wrapped in code fences / surrounding prose."""
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError(f"no JSON object in judge output: {text[:200]!r}")
    return Verdict.model_validate(json.loads(match.group(0)))


def judge_answer(
    llm: BaseChatModel,
    question: str,
    reference: str,
    answer: str,
    language: str,
    attempts: int = 2,
) -> Verdict:
    prompt = JUDGE_PROMPT.format(
        language=LANGUAGE_NAMES.get(language, language),
        question=question,
        reference=reference,
        answer=answer,
    )
    last: Exception | None = None
    for _ in range(attempts):
        raw = _text(invoke_with_retry(llm, [HumanMessage(content=prompt)]))
        try:
            return parse_verdict(raw)
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last = exc
    raise ValueError(f"judge returned unparseable output twice: {last}")


def agreement(rows_a: list[dict], rows_b: list[dict]) -> dict[str, object]:
    """Compare two judges on the answers both have judged (keyed by id and language):
    exact verdict agreement, mean absolute score difference and the confusion counts."""
    a = {(r["id"], r["lang"]): r for r in rows_a}
    b = {(r["id"], r["lang"]): r for r in rows_b}
    common = sorted(a.keys() & b.keys())
    if not common:
        return {"n": 0}
    confusion: dict[str, int] = {}
    for k in common:
        key = f"{a[k]['verdict']} -> {b[k]['verdict']}"
        confusion[key] = confusion.get(key, 0) + 1
    exact = sum(a[k]["verdict"] == b[k]["verdict"] for k in common) / len(common)
    mad = sum(abs(SCORES[a[k]["verdict"]] - SCORES[b[k]["verdict"]]) for k in common) / len(common)
    mean_a = sum(SCORES[a[k]["verdict"]] for k in common) / len(common)
    mean_b = sum(SCORES[b[k]["verdict"]] for k in common) / len(common)
    return {
        "n": len(common),
        "exact_agreement": round(exact, 3),
        "mean_abs_score_diff": round(mad, 3),
        "mean_score_a": round(mean_a, 3),
        "mean_score_b": round(mean_b, 3),
        "confusion": dict(sorted(confusion.items())),
    }
