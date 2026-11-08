"""Idempotent builds and cache -> Chroma rebuilds, all with fake embeddings."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
import yaml
from langchain_core.embeddings import DeterministicFakeEmbedding

from compliance_assistant.config import Settings
from compliance_assistant.ingestion import SourceDoc
from compliance_assistant.vectorstore import (
    EmbeddingCache,
    build_kb,
    build_or_load,
    embed_missing,
    load_manifest,
    rebuild_chroma,
)


class CountingEmbedding(DeterministicFakeEmbedding):
    """Fake embedder that counts API-equivalent calls."""

    calls: int = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return super().embed_documents(texts)


@pytest.fixture
def kb(settings: Settings, source: SourceDoc) -> Settings:
    """Settings whose sources.yaml lists the fixture document."""
    doc = {
        "doc_id": source.doc_id,
        "title": source.title,
        "short_cite": source.short_cite,
        "url": source.url,
        "section_style": "ich",
    }
    settings.sources_path.write_text(yaml.safe_dump({"documents": [doc]}), encoding="utf-8")
    return settings


def test_dry_run_counts_without_embedding(kb: Settings) -> None:
    report = build_kb(kb, None, dry_run=True)
    assert report.chunks_per_doc["test_e9x"] > 0
    assert report.total_embedded == 0
    assert not kb.manifest_path.exists()


def test_build_is_idempotent(kb: Settings) -> None:
    embedder = CountingEmbedding(size=8)
    first = build_kb(kb, embedder, sleep=lambda _: None)
    assert first.total_embedded == first.total_chunks > 0
    calls_after_first = embedder.calls
    assert calls_after_first >= 1

    second = build_kb(kb, embedder, sleep=lambda _: None)
    assert second.total_embedded == 0, "second build must not embed anything"
    assert embedder.calls == calls_after_first

    manifest = load_manifest(kb)
    entry = manifest["test_e9x"]
    assert entry["n_chunks"] == first.total_chunks
    assert entry["chunk_size"] == kb.chunk_size


def test_changed_chunking_invalidates_cache(kb: Settings) -> None:
    embedder = CountingEmbedding(size=8)
    build_kb(kb, embedder, sleep=lambda _: None)
    from dataclasses import replace

    rechunked = replace(kb, chunk_size=150, chunk_overlap=10)
    report = build_kb(rechunked, embedder, sleep=lambda _: None)
    assert report.total_embedded == report.total_chunks > 0
    assert load_manifest(rechunked)["test_e9x"]["chunk_size"] == 150


def test_embed_missing_is_resumable(settings: Settings) -> None:
    from compliance_assistant.ingestion import Chunk

    cache = EmbeddingCache(settings.cache_dir)
    chunks = [Chunk(f"d:p1:c{i}:{i:08d}", f"text {i}", {"page": 1}) for i in range(5)]
    embedder = CountingEmbedding(size=4)
    assert embed_missing("d", chunks[:3], embedder, cache, batch_size=2, sleep=lambda _: None) == 3
    assert embed_missing("d", chunks, embedder, cache, batch_size=2, sleep=lambda _: None) == 2
    assert len(cache.load("d")) == 5
    with gzip.open(cache.path("d"), "rt") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    assert len(rows) == 5 and len(rows[0]["vector"]) == 4


def test_stale_cache_entries_are_pruned(settings: Settings) -> None:
    from compliance_assistant.ingestion import Chunk

    cache = EmbeddingCache(settings.cache_dir)
    old = [Chunk(f"d:p1:c{i}:old{i:05d}", f"old {i}", {}) for i in range(3)]
    embed_missing("d", old, CountingEmbedding(size=4), cache, sleep=lambda _: None)
    new = [*old[:1], Chunk("d:p1:c1:new00001", "new 1", {})]
    embedder = CountingEmbedding(size=4)
    assert embed_missing("d", new, embedder, cache, sleep=lambda _: None) == 1
    assert set(cache.load("d")) == {c.id for c in new}


def test_rate_limit_retries_then_succeeds(settings: Settings) -> None:
    from compliance_assistant.ingestion import Chunk

    failures = [2]

    class Flaky(DeterministicFakeEmbedding):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            if failures[0]:
                failures[0] -= 1
                raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
            return super().embed_documents(texts)

    waits: list[float] = []
    cache = EmbeddingCache(settings.cache_dir)
    chunks = [Chunk("d:p1:c0:00000000", "hello", {})]
    assert embed_missing("d", chunks, Flaky(size=4), cache, sleep=waits.append) == 1
    assert waits == [10.0, 20.0]


def test_rebuild_chroma_from_cache_needs_no_embedding_calls(kb: Settings) -> None:
    doc_embedder = CountingEmbedding(size=8)
    build_kb(kb, doc_embedder, sleep=lambda _: None)
    query_embedder = CountingEmbedding(size=8)

    store = rebuild_chroma(kb, query_embedder)
    assert store._collection.count() == load_manifest(kb)["test_e9x"]["n_chunks"]
    assert query_embedder.calls == 0, "rebuild must insert precomputed vectors"

    hits = store.similarity_search("7 calendar days", k=2)
    assert hits and all(h.metadata["doc_id"] == "test_e9x" for h in hits)

    # Second open reuses the persisted collection instead of rebuilding.
    stamp = (kb.chroma_dir / ".built_from").stat().st_mtime
    again = build_or_load(kb, query_embedder)
    assert again._collection.count() == store._collection.count()
    assert (kb.chroma_dir / ".built_from").stat().st_mtime == stamp


def test_missing_pdf_is_reported_not_fatal(kb: Settings) -> None:
    Path(kb.raw_dir / "test_e9x.pdf").unlink()
    report = build_kb(kb, None, dry_run=True)
    assert report.skipped == ["test_e9x"]


def test_cached_query_embeddings_hit_disk_cache(settings: Settings) -> None:
    from compliance_assistant.vectorstore import CachedQueryEmbeddings

    inner = CountingEmbedding(size=4)
    path = settings.kb_dir / "query_cache.jsonl.gz"
    cache = CachedQueryEmbeddings(inner, path, model="m1")
    v1 = cache.embed_query("susar timeline")
    v2 = cache.embed_query("susar timeline")
    assert v1 == v2 and cache.hits == 1 and cache.misses == 1

    reloaded = CachedQueryEmbeddings(CountingEmbedding(size=4), path, model="m1")
    assert reloaded.embed_query("susar timeline") == v1 and reloaded.misses == 0
    other_model = CachedQueryEmbeddings(CountingEmbedding(size=4), path, model="m2")
    other_model.embed_query("susar timeline")
    assert other_model.misses == 1, "a different model must not reuse cached vectors"
