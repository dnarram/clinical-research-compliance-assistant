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


def test_not_in_kb_and_all_docs_required(tmp_path: Path) -> None:
    rows = [
        {
            "id": "multi",
            "type": "in_domain",
            "question_en": "reporting timeline comparison",
            "expected_doc_ids": ["ich_e2a", "ich_e6_r3"],
            "all_docs_required": True,
        },
        {
            "id": "cfr",
            "type": "not_in_kb",
            "question_en": "What does 21 CFR say about reporting?",
        },
    ]
    path = tmp_path / "g.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    items = load_golden(path)
    answers = {
        "reporting timeline comparison": "both [1][2]",
        "What does 21 CFR say about reporting?": "I could not find this in my knowledge base.",
    }
    report = evaluate_retrieval(
        KeywordStore(), items, Settings(k=2), threshold=0.6, answer_fn=answers.__getitem__
    )
    by_id = {r.id: r for r in report.results}
    assert by_id["multi"].doc_hit is True, "both expected docs are in the top-2"
    assert by_id["cfr"].grounded is True and by_id["cfr"].honest_not_found is True
    assert report.metrics()["not_in_kb_honesty"] == 1.0
    assert "| cfr | en | not_in_kb | yes |" in report.to_markdown()


def test_keyword_matching_normalises_quotes_and_accepts_variants() -> None:
    from compliance_assistant.evaluation import keyword_found, normalise

    answer = normalise(
        "Per the Investigator\u2019s Brochure, it requires inpatient hospitalisation."
    )
    assert keyword_found("Investigator's Brochure", answer)
    assert keyword_found("hospitalization|hospitalisation", answer)
    assert not keyword_found("hospitalization", answer)
    assert keyword_found(
        "15 calendar days|15 días naturales", normalise("en un plazo de 15 días naturales")
    )


def test_whole_word_matching_and_tagged_sections() -> None:
    from compliance_assistant.evaluation import keyword_found, normalise, section_hit

    assert not keyword_found("IB", normalise("es posible que ocurra"))
    assert keyword_found(
        "Investigator's Brochure|IB", normalise("más grave de lo descrito en el IB [2]")
    )
    assert keyword_found(
        "regulatory authority", normalise("to the regulatory authority(ies) of all SUSARs")
    )

    retrieved = {("ich_e6_r3", "2.8.1"), ("wma_helsinki_2024", "28")}
    tagged = ("ich_e6_r3:2.8.13", "wma_helsinki_2024:28")
    docs = ("ich_e6_r3", "wma_helsinki_2024")
    assert section_hit(tagged, retrieved, docs, all_docs=False), "any section is enough"
    assert not section_hit(tagged, retrieved, docs, all_docs=True), "E6(R3) §2.8.13 missing"
    assert section_hit(tagged, retrieved | {("ich_e6_r3", "2.8.13")}, docs, all_docs=True)
    assert section_hit(("1",), {("ich_e2a", "1")}, ("ich_e2a",), all_docs=False)
    assert not section_hit(
        ("ich_e2a:1",), {("wma_helsinki_2024", "1")}, ("ich_e2a",), all_docs=False
    )


def test_plural_endings_are_accepted() -> None:
    from compliance_assistant.evaluation import keyword_found, normalise

    text = normalise("their legally acceptable representatives, acting in the best interest")
    assert keyword_found("legally acceptable representative", text)
    assert not keyword_found("legally acceptable representative", normalise("representativeness"))


def test_honesty_cues_cover_graded_spanish_phrasing() -> None:
    from compliance_assistant.evaluation import NOT_FOUND_CUES, normalise

    text = normalise(
        "No puedo responder completamente, ya que el texto de ICH E9(R1) no se incluye en las fuentes."
    )
    assert any(cue in text for cue in NOT_FOUND_CUES)
