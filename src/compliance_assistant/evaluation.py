"""Evaluation harness over the hand-written golden set (data/eval/golden.jsonl).

Retrieval metrics need only query embeddings (one request per question and language).
Answer metrics (`answer_fn` given) run the full agent and cost one or two LLM calls per
question, so they are opt-in.

Item types:
- ``in_domain``  — must be grounded; expected documents/sections must be retrieved.
- ``ood``        — must be refused by the retrieval gate (not grounded).
- ``not_in_kb``  — looks in-domain (retrieval may well be grounded) but asks about a
  document the knowledge base does not hold; the *answer* must say so instead of
  inventing content. Scored only when answers are generated.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.vectorstores import VectorStore

from compliance_assistant.config import Settings
from compliance_assistant.retrieval import retrieve

LANGUAGES = ("en", "es")
TYPES = ("in_domain", "ood", "not_in_kb")
# Phrases that signal an honest "not in my knowledge base" answer (EN/ES).
NOT_FOUND_CUES = (
    "could not find",
    "couldn't find",
    "not in my knowledge base",
    "does not contain",
    "doesn't contain",
    "not contain information",
    "no he encontrado",
    "no pude encontrar",
    "no encontré",
    "no contiene",
    "no está en mi base",
    "no se encuentra en mi base",
)


@dataclass(frozen=True)
class GoldenItem:
    id: str
    type: str
    questions: dict[str, str]  # language -> question
    expected_doc_ids: tuple[str, ...] = ()
    expected_sections: tuple[str, ...] = ()
    expected_keywords: tuple[str, ...] = ()
    all_docs_required: bool = False  # multi-source items: every expected doc must appear
    notes: str = ""


def load_golden(path: Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d["type"] not in TYPES:
            raise ValueError(f"{d['id']}: type must be one of {TYPES}")
        items.append(
            GoldenItem(
                id=d["id"],
                type=d["type"],
                questions={
                    lang: d[f"question_{lang}"] for lang in LANGUAGES if d.get(f"question_{lang}")
                },
                expected_doc_ids=tuple(d.get("expected_doc_ids", [])),
                expected_sections=tuple(str(s) for s in d.get("expected_sections", [])),
                expected_keywords=tuple(d.get("expected_keywords", [])),
                all_docs_required=bool(d.get("all_docs_required", False)),
                notes=d.get("notes", ""),
            )
        )
    return items


@dataclass
class ItemResult:
    id: str
    type: str
    language: str
    question: str
    grounded: bool
    max_score: float
    retrieved: list[str]  # "doc_id §section"
    doc_hit: bool | None  # None when not applicable
    section_hit: bool | None
    answer: str | None = None
    keyword_coverage: float | None = None
    honest_not_found: bool | None = None  # not_in_kb items, only with answers


@dataclass
class EvalReport:
    k: int
    threshold: float | None
    results: list[ItemResult] = field(default_factory=list)

    def _subset(self, type_: str, language: str | None = None) -> list[ItemResult]:
        return [
            r
            for r in self.results
            if r.type == type_ and (language is None or r.language == language)
        ]

    def metrics(self) -> dict[str, float | None]:
        def rate(xs: list[bool]) -> float | None:
            return round(sum(xs) / len(xs), 3) if xs else None

        m: dict[str, float | None] = {}
        for lang in LANGUAGES:
            in_dom = self._subset("in_domain", lang)
            m[f"doc_hit_rate@{self.k}_{lang}"] = rate(
                [bool(r.doc_hit) for r in in_dom if r.doc_hit is not None]
            )
            m[f"section_hit_rate@{self.k}_{lang}"] = rate(
                [bool(r.section_hit) for r in in_dom if r.section_hit is not None]
            )
            m[f"false_refusal_rate_{lang}"] = rate([not r.grounded for r in in_dom])
            m[f"refusal_accuracy_{lang}"] = rate(
                [not r.grounded for r in self._subset("ood", lang)]
            )
        covered = [r.keyword_coverage for r in self.results if r.keyword_coverage is not None]
        m["keyword_coverage"] = round(statistics.mean(covered), 3) if covered else None
        honest = [r.honest_not_found for r in self.results if r.honest_not_found is not None]
        m["not_in_kb_honesty"] = rate([bool(h) for h in honest])
        return m

    def to_markdown(self) -> str:
        lines = [
            f"# Evaluation (k={self.k}, threshold={self.threshold})",
            "",
            "| metric | value |",
            "|---|---|",
        ]
        lines += [f"| {k} | {'n/a' if v is None else v} |" for k, v in self.metrics().items()]
        lines += [
            "",
            "| id | lang | type | grounded | max score | doc hit | section hit | keywords | honest | retrieved |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]

        def yn(v: bool | None) -> str:
            return "-" if v is None else ("yes" if v else "NO")

        for r in self.results:
            kw = "-" if r.keyword_coverage is None else f"{r.keyword_coverage:.0%}"
            lines.append(
                f"| {r.id} | {r.language} | {r.type} | {'yes' if r.grounded else 'no'} | "
                f"{r.max_score:.3f} | {yn(r.doc_hit)} | {yn(r.section_hit)} | {kw} | "
                f"{yn(r.honest_not_found)} | {', '.join(r.retrieved[:3])} |"
            )
        return "\n".join(lines) + "\n"


def evaluate_retrieval(
    vectorstore: VectorStore,
    items: list[GoldenItem],
    settings: Settings,
    threshold: float | None,
    answer_fn: Callable[[str], str] | None = None,
) -> EvalReport:
    """Score every golden question in every language. `answer_fn(question) -> text`
    enables keyword coverage and the not-in-KB honesty check (it is the agent's `ask`,
    so it costs LLM calls)."""
    report = EvalReport(k=settings.k, threshold=threshold)
    for item in items:
        for lang, question in item.questions.items():
            result = retrieve(vectorstore, question, settings, threshold=threshold)
            docs = result.docs or [
                d
                for d, _ in vectorstore.similarity_search_with_relevance_scores(
                    question, k=settings.k
                )
            ]
            retrieved = [
                f"{d.metadata.get('doc_id')} §{d.metadata.get('section', '')}".rstrip(" §")
                for d in docs
            ]
            doc_ids = {d.metadata.get("doc_id") for d in docs}
            sections = {str(d.metadata.get("section", "")) for d in docs}
            doc_hit = section_hit = None
            if item.type == "in_domain" and item.expected_doc_ids:
                expected = set(item.expected_doc_ids)
                doc_hit = (
                    expected <= doc_ids if item.all_docs_required else bool(expected & doc_ids)
                )
            if item.type == "in_domain" and item.expected_sections:
                section_hit = any(s in sections for s in item.expected_sections)
            r = ItemResult(
                item.id,
                item.type,
                lang,
                question,
                result.grounded,
                result.max_score,
                retrieved,
                doc_hit,
                section_hit,
            )
            if answer_fn is not None and item.type in ("in_domain", "not_in_kb"):
                r.answer = answer_fn(question)
                low = r.answer.lower()
                if item.type == "in_domain" and item.expected_keywords:
                    r.keyword_coverage = sum(
                        kw.lower() in low for kw in item.expected_keywords
                    ) / len(item.expected_keywords)
                if item.type == "not_in_kb":
                    r.honest_not_found = any(cue in low for cue in NOT_FOUND_CUES)
            report.results.append(r)
    return report


def summarise(report: EvalReport) -> dict[str, Any]:
    return {"n_results": len(report.results), **report.metrics()}
