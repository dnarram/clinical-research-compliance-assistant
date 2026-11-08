"""Retrieval over the Chroma collection: scoring, the relevance gate, MMR and citations.

Two searches per question:

1. `similarity_search_with_relevance_scores` gives cosine relevance (1 - distance) for the
   top-k. Its maximum is the **grounding signal**: below the calibrated threshold the
   question is treated as out of scope and the graph routes to `refuse` without calling
   the LLM.
2. `max_marginal_relevance_search` picks the chunks actually sent to the LLM: MMR trades
   a little similarity for diversity, which matters when the answer spans several
   documents (E6(R3) + Helsinki on consent, E2A + E6(R3) on safety reporting).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from compliance_assistant.config import Settings


@dataclass(frozen=True)
class Source:
    """One retrieved chunk as shown to the user and referenced as [n] in the answer."""

    n: int
    doc_id: str
    short_cite: str
    section: str
    page: int
    url: str
    text: str
    score: float | None = None

    @property
    def citation(self) -> str:
        return cite(
            {
                "short_cite": self.short_cite,
                "section": self.section,
                "page": self.page,
                "doc_id": self.doc_id,
            }
        )


@dataclass
class RetrievalResult:
    docs: list[Document]
    scores: list[float]
    max_score: float
    grounded: bool
    threshold: float | None
    sources: list[Source] = field(default_factory=list)


def cite(meta: dict[str, Any]) -> str:
    """Human citation: 'ICH E6(R3) §2.11.3, p.14' or 'Declaration of Helsinki (2024) ¶26'."""
    short = meta.get("short_cite", meta.get("doc_id", "?"))
    section = meta.get("section") or ""
    page = meta.get("page")
    if str(meta.get("doc_id", "")).startswith("wma_"):
        return f"{short} ¶{section}" if section else short
    text = f"{short} §{section}" if section else short
    return f"{text}, p.{page}" if page else text


def scored_search(vs: VectorStore, query: str, k: int) -> list[tuple[Document, float]]:
    return vs.similarity_search_with_relevance_scores(query, k=k)


def mmr_search(vs: VectorStore, query: str, settings: Settings) -> list[Document]:
    return vs.max_marginal_relevance_search(
        query, k=settings.k, fetch_k=settings.fetch_k, lambda_mult=settings.mmr_lambda
    )


def retrieve(
    vs: VectorStore, query: str, settings: Settings, threshold: float | None = None
) -> RetrievalResult:
    """Score, gate, then diversify. `threshold=None` disables the gate (used before the
    calibration exists and in tests)."""
    scored = scored_search(vs, query, settings.k)
    scores = [s for _, s in scored]
    max_score = max(scores, default=0.0)
    grounded = threshold is None or max_score >= threshold
    if not grounded:
        return RetrievalResult([], scores, max_score, False, threshold)
    docs = mmr_search(vs, query, settings)
    by_text = {d.page_content: s for d, s in scored}
    doc_scores = [by_text.get(d.page_content, 0.0) for d in docs]
    result = RetrievalResult(docs, doc_scores, max_score, True, threshold)
    result.sources = to_sources(docs, doc_scores)
    return result


def to_sources(docs: list[Document], scores: list[float] | None = None) -> list[Source]:
    out: list[Source] = []
    for i, d in enumerate(docs, start=1):
        m = d.metadata
        out.append(
            Source(
                n=i,
                doc_id=str(m.get("doc_id", "")),
                short_cite=str(m.get("short_cite", "")),
                section=str(m.get("section", "")),
                page=int(m.get("page", 0) or 0),
                url=str(m.get("url", "")),
                text=d.page_content,
                score=(scores[i - 1] if scores else None),
            )
        )
    return out


def format_context(sources: list[Source]) -> str:
    """Numbered context blocks for the prompt; the numbers are what the answer cites."""
    blocks = [f"[{s.n}] {s.citation}\n{s.text}" for s in sources]
    return "\n\n".join(blocks)
