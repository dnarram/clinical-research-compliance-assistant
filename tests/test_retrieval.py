from __future__ import annotations

from langchain_core.documents import Document

from compliance_assistant.config import Settings
from compliance_assistant.retrieval import (
    RetrievalResult,
    cite,
    format_context,
    retrieve,
    to_sources,
)


class StubStore:
    """Minimal vector-store double: fixed ranked results with scores."""

    def __init__(self, ranked: list[tuple[Document, float]]) -> None:
        self.ranked = ranked

    def similarity_search_with_relevance_scores(
        self, query: str, k: int = 4
    ) -> list[tuple[Document, float]]:
        return self.ranked[:k]

    def max_marginal_relevance_search(
        self, query: str, k: int = 4, fetch_k: int = 20, lambda_mult: float = 0.5
    ):
        return [d for d, _ in self.ranked[:k]]


def _doc(text: str, **meta) -> Document:
    base = {
        "doc_id": "ich_e6_r3",
        "short_cite": "ICH E6(R3)",
        "section": "2.11.3",
        "page": 14,
        "url": "u",
    }
    return Document(page_content=text, metadata={**base, **meta})


def test_cite_formats_ich_and_helsinki() -> None:
    assert cite(
        {"doc_id": "ich_e6_r3", "short_cite": "ICH E6(R3)", "section": "2.11.3", "page": 14}
    ) == ("ICH E6(R3) §2.11.3, p.14")
    assert (
        cite({"doc_id": "ich_e2a", "short_cite": "ICH E2A", "section": "", "page": 5})
        == "ICH E2A, p.5"
    )
    assert cite(
        {
            "doc_id": "wma_helsinki_2024",
            "short_cite": "Declaration of Helsinki (2024)",
            "section": "26",
        }
    ) == ("Declaration of Helsinki (2024) ¶26")


def test_gate_refuses_below_threshold() -> None:
    store = StubStore([(_doc("consent text"), 0.31), (_doc("other"), 0.20)])
    result = retrieve(store, "q", Settings(), threshold=0.5)
    assert isinstance(result, RetrievalResult)
    assert result.grounded is False and result.docs == [] and result.max_score == 0.31


def test_gate_passes_and_sources_are_numbered() -> None:
    store = StubStore(
        [
            (_doc("consent text"), 0.72),
            (
                _doc(
                    "helsinki",
                    doc_id="wma_helsinki_2024",
                    short_cite="Declaration of Helsinki (2024)",
                    section="26",
                ),
                0.65,
            ),
        ]
    )
    result = retrieve(store, "q", Settings(k=2), threshold=0.5)
    assert result.grounded and len(result.sources) == 2
    assert [s.n for s in result.sources] == [1, 2]
    assert result.sources[0].score == 0.72
    ctx = format_context(result.sources)
    assert ctx.startswith("[1] ICH E6(R3) §2.11.3, p.14\nconsent text")
    assert "[2] Declaration of Helsinki (2024) ¶26" in ctx


def test_no_threshold_means_always_grounded() -> None:
    store = StubStore([(_doc("x"), 0.05)])
    assert retrieve(store, "q", Settings(k=1), threshold=None).grounded


def test_to_sources_tolerates_missing_metadata() -> None:
    src = to_sources([Document(page_content="bare")])[0]
    assert src.n == 1 and src.page == 0 and src.citation == ""
