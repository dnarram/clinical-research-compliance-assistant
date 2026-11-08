from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.documents import Document

from compliance_assistant.config import Settings
from compliance_assistant.evaluation import evaluate_retrieval, load_golden


class KeywordStore:
    """Returns the E2A doc with a high score when the query mentions reporting, else low."""

    def __init__(self) -> None:
        self.e2a = Document(
            page_content="7 calendar days", metadata={"doc_id": "ich_e2a", "section": "1"}
        )
        self.other = Document(
            page_content="unrelated", metadata={"doc_id": "ich_e6_r3", "section": "9.1"}
        )

    def similarity_search_with_relevance_scores(self, query: str, k: int = 4):
        hit = any(w in query.lower() for w in ("report", "notific"))
        return [(self.e2a, 0.9), (self.other, 0.8)] if hit else [(self.other, 0.4)]

    def max_marginal_relevance_search(
        self, query: str, k: int = 4, fetch_k: int = 20, lambda_mult: float = 0.5
    ):
        return [d for d, _ in self.similarity_search_with_relevance_scores(query, k)]


def _golden(tmp_path: Path) -> Path:
    rows = [
        {
            "id": "timeline",
            "type": "in_domain",
            "question_en": "What is the reporting timeline?",
            "question_es": "¿Cuál es el plazo de notificación?",
            "expected_doc_ids": ["ich_e2a"],
            "expected_sections": ["1"],
            "expected_keywords": ["7 calendar days"],
        },
        {
            "id": "paella",
            "type": "ood",
            "question_en": "Best paella recipe?",
            "question_es": "¿Mejor receta de paella?",
        },
    ]
    path = tmp_path / "golden.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_load_golden_validates_type(tmp_path: Path) -> None:
    bad = tmp_path / "g.jsonl"
    bad.write_text(json.dumps({"id": "x", "type": "weird", "question_en": "q"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_golden(bad)


def test_metrics_per_language_and_refusals(tmp_path: Path) -> None:
    items = load_golden(_golden(tmp_path))
    settings = Settings(k=2)
    report = evaluate_retrieval(KeywordStore(), items, settings, threshold=0.6)
    m = report.metrics()
    assert m["doc_hit_rate@2_en"] == 1.0 and m["doc_hit_rate@2_es"] == 1.0
    assert m["section_hit_rate@2_en"] == 1.0
    assert m["refusal_accuracy_en"] == 1.0 and m["refusal_accuracy_es"] == 1.0
    assert m["false_refusal_rate_en"] == 0.0
    assert m["keyword_coverage"] is None
    md = report.to_markdown()
    assert "| timeline | en | in_domain | yes |" in md and "| paella | es | ood | no |" in md


def test_keyword_coverage_uses_answer_fn(tmp_path: Path) -> None:
    items = load_golden(_golden(tmp_path))
    calls: list[str] = []

    def answer(q: str) -> str:
        calls.append(q)
        return "Within 7 calendar days [1]."

    report = evaluate_retrieval(
        KeywordStore(), items, Settings(k=2), threshold=0.6, answer_fn=answer
    )
    assert report.metrics()["keyword_coverage"] == 1.0
    assert len(calls) == 2, "answers are generated only for in_domain items (both languages)"
