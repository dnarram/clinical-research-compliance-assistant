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


# --- context expansion and document routing -----------------------------------------------

from compliance_assistant.retrieval import (  # noqa: E402
    ContextIndex,
    expand,
    named_documents,
    routed_search,
)


class ListingStore:
    """Store double that exposes `.get()` like langchain-chroma, plus filtered MMR."""

    def __init__(self, chunks: list[tuple[str, dict]]) -> None:
        self.chunks = chunks
        self.mmr_calls: list[dict] = []

    def get(self, include=None):
        return {"documents": [t for t, _ in self.chunks], "metadatas": [m for _, m in self.chunks]}

    def max_marginal_relevance_search(self, query: str, k: int = 4, **kwargs):
        self.mmr_calls.append({"k": k, **kwargs})
        flt = kwargs.get("filter")
        docs = [
            Document(page_content=t, metadata=m)
            for t, m in self.chunks
            if not flt or m["doc_id"] == flt["doc_id"]
        ]
        return docs[:k]


def _meta(doc: str, page: int, idx: int, section: str) -> dict:
    return {
        "doc_id": doc,
        "short_cite": doc.upper(),
        "page": page,
        "chunk_index": idx,
        "section": section,
        "url": "",
    }


SHORT_LIST = [
    (
        "2.8.10 The consent should explain: (a) The purpose of the trial;",
        _meta("e6", 24, 6, "2.8.10"),
    ),
    ("(e) What is expected of the participants;", _meta("e6", 24, 7, "2.8.10")),
    ("(f) The reasonably foreseeable risks;", _meta("e6", 25, 0, "2.8.10")),
    (
        "2.8.11 Prior to participation the participant should receive a copy.",
        _meta("e6", 25, 1, "2.8.11"),
    ),
]


def test_short_section_is_expanded_whole_across_pages() -> None:
    index = ContextIndex.from_store(ListingStore(SHORT_LIST), section_budget=3000)
    hit = Document(page_content=SHORT_LIST[1][0], metadata=SHORT_LIST[1][1])
    docs, scores = expand([hit], [0.8], index)
    assert len(docs) == 1 and scores == [0.8]
    text = docs[0].page_content
    assert "(a) The purpose" in text and "(f) The reasonably foreseeable" in text
    assert "2.8.11" not in text, "expansion stays inside the section"
    src = to_sources(docs)[0]
    assert src.citation == "E6 §2.8.10, pp.24\u201325"


def test_long_section_gets_neighbours_only_and_hits_merge() -> None:
    long = [(f"chunk {i} " + "x" * 400, _meta("e2a", 5, i, "3")) for i in range(10)]
    index = ContextIndex.from_store(ListingStore(long), section_budget=1000)
    hits = [Document(page_content=long[i][0], metadata=long[i][1]) for i in (4, 5, 9)]
    docs, scores = expand(hits, [0.9, 0.7, 0.6], index)
    assert len(docs) == 2, "hits 4 and 5 overlap and are merged"
    assert "chunk 3" in docs[0].page_content and "chunk 6" in docs[0].page_content
    assert "chunk 2" not in docs[0].page_content
    assert scores == [0.9, 0.6]


def test_overlap_between_chunks_is_not_duplicated() -> None:
    from compliance_assistant.retrieval import _join

    assert _join(
        "results in death, is life-threatening", "is life-threatening, requires hospitalisation"
    ) == ("results in death, is life-threatening, requires hospitalisation")


def test_store_without_listing_disables_expansion() -> None:
    assert ContextIndex.from_store(StubStore([])) is None


def test_named_documents_uses_aliases_from_sources_yaml() -> None:
    s = Settings()
    assert named_documents("Compare ICH E6(R3) and the Declaration of Helsinki on consent", s) == [
        "ich_e6_r3",
        "wma_helsinki_2024",
    ]
    assert named_documents("How does ICH E2A define serious?", s) == ["ich_e2a"]
    assert named_documents("What is a SUSAR?", s) == []


def test_routed_search_shares_k_between_named_documents() -> None:
    chunks = [(f"e6 {i}", _meta("ich_e6_r3", 1, i, "1")) for i in range(5)] + [
        (f"doh {i}", _meta("wma_helsinki_2024", 1, i, "28")) for i in range(5)
    ]
    store = ListingStore(chunks)
    docs = routed_search(store, "q", Settings(k=6), ["ich_e6_r3", "wma_helsinki_2024"])
    assert len(docs) == 6
    assert {d.metadata["doc_id"] for d in docs} == {"ich_e6_r3", "wma_helsinki_2024"}
    assert [c["filter"]["doc_id"] for c in store.mmr_calls] == ["ich_e6_r3", "wma_helsinki_2024"]

    single = ListingStore(chunks)
    routed_search(single, "q", Settings(k=6), ["ich_e2a"])
    assert single.mmr_calls[0]["k"] == 4 and "filter" not in single.mmr_calls[1], "two free slots"
