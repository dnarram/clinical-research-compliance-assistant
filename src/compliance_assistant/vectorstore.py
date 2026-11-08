"""Embeddings cache, build manifest and the ChromaDB collection.

Design (see CLAUDE.md invariants 1-3):

* The **versioned cache** `data/kb/embeddings/<doc_id>.jsonl.gz` holds every chunk's
  text, metadata and vector. It is the source of truth; the Chroma directory is a
  derived artefact that is rebuilt from the cache in seconds with zero API calls.
* `data/kb/manifest.json` records, per document, what the cache was built from
  (PDF sha256, embedding model + dimension, chunking parameters). A document is only
  re-embedded when one of those changes, so repeated builds cost nothing.
* Documents and queries use *different* embedding instances: `RETRIEVAL_DOCUMENT` for
  indexing and `RETRIEVAL_QUERY` at search time (asymmetric retrieval), on the models
  that support the `task_type` hint.
"""

from __future__ import annotations

import gzip
import json
import logging
import shutil
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from compliance_assistant.config import Settings
from compliance_assistant.ingestion import Chunk, SourceDoc, ingest, load_sources, sha256_of

log = logging.getLogger(__name__)

TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"


# --- Gemini embeddings ------------------------------------------------------------------


def is_daily_quota(exc: Exception) -> bool:
    """A per-day free-tier quota error: waiting does not help, switching project keys does."""
    text = str(exc)
    return ("429" in text or "RESOURCE_EXHAUSTED" in text) and (
        "per day" in text.lower() or "PerDay" in text
    )


class FailoverEmbeddings(Embeddings):
    """Round-robin-on-failure over several embeddings clients (one per API key).

    Only a *daily* quota error moves to the next client; per-minute limits are retried by
    the callers. Once switched, it stays on the new client for the process lifetime."""

    def __init__(self, clients: list[Embeddings]) -> None:
        if not clients:
            raise ValueError("at least one embeddings client is required")
        self.clients = clients
        self.index = 0

    def _call(self, method: str, *args: Any) -> Any:
        while True:
            try:
                return getattr(self.clients[self.index], method)(*args)
            except Exception as exc:
                if is_daily_quota(exc) and self.index + 1 < len(self.clients):
                    self.index += 1
                    log.warning(
                        "[embed] daily quota hit; switching to backup key #%d", self.index + 1
                    )
                    continue
                raise

    def embed_query(self, text: str) -> list[float]:
        return self._call("embed_query", text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call("embed_documents", texts)


def get_embeddings(settings: Settings, api_key: str | list[str], task_type: str) -> Embeddings:
    """A Gemini embeddings client for one role (documents or queries).

    Asymmetric retrieval: the index is built with RETRIEVAL_DOCUMENT and searched with
    RETRIEVAL_QUERY. `gemini-embedding-001` uses the hint to shape the vectors;
    `gemini-embedding-2` accepts it (verified 2026-11-07) but its documentation says the
    hint is not applied, so with that model the two roles coincide — harmless, and the
    code stays correct if the model is switched.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    keys = [api_key] if isinstance(api_key, str) else list(api_key)
    clients: list[Embeddings] = [
        GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=key,
            output_dimensionality=settings.embedding_dim,
            task_type=task_type,
        )
        for key in keys
    ]
    return clients[0] if len(clients) == 1 else FailoverEmbeddings(clients)


class CachedQueryEmbeddings(Embeddings):
    """Wraps the query embedder with a persistent text -> vector cache.

    The free tier counts every embedded text against a daily limit (1,000 with
    `gemini-embedding-2`, and the 800-chunk corpus build alone uses ~800). Demo and golden
    questions are asked many times; caching their vectors makes repeated runs — and the
    scripted live demo — cost zero embedding requests. The cache is keyed on the exact
    query text and tagged with the model so a model switch invalidates it.
    """

    def __init__(self, inner: Embeddings, path: Path, model: str) -> None:
        self.inner = inner
        self.path = path
        self.model = model
        self._cache: dict[str, list[float]] = {}
        self.hits = 0
        self.misses = 0
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        d = json.loads(line)
                        if d.get("model") == model:
                            self._cache[d["text"]] = d["vector"]

    def embed_query(self, text: str) -> list[float]:
        if text in self._cache:
            self.hits += 1
            return self._cache[text]
        # Rounded once so the in-memory value equals what is read back from disk.
        vector = [round(float(x), 6) for x in self.inner.embed_query(text)]
        self.misses += 1
        self._cache[text] = vector
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.path, "at", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"model": self.model, "text": text, "vector": vector},
                    ensure_ascii=False,
                )
                + "\n"
            )
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]


def get_query_embeddings(settings: Settings, api_key: str | list[str]) -> Embeddings:
    """The query-side embedder every consumer should use: Gemini + persistent cache."""
    return CachedQueryEmbeddings(
        get_embeddings(settings, api_key, TASK_QUERY),
        settings.query_cache_path,
        settings.embedding_model,
    )


# --- cache ---------------------------------------------------------------------------------


@dataclass
class EmbeddingRecord:
    id: str
    text: str
    metadata: dict[str, Any]
    vector: list[float]


class EmbeddingCache:
    """One gzipped JSON-lines file per document. Append-only during a build, rewritten
    when a document's inputs change."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def path(self, doc_id: str) -> Path:
        return self.cache_dir / f"{doc_id}.jsonl.gz"

    def load(self, doc_id: str) -> dict[str, EmbeddingRecord]:
        path = self.path(doc_id)
        if not path.exists():
            return {}
        records: dict[str, EmbeddingRecord] = {}
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    d = json.loads(line)
                    records[d["id"]] = EmbeddingRecord(
                        d["id"], d["text"], d["metadata"], d["vector"]
                    )
        return records

    def append(self, doc_id: str, records: Iterable[EmbeddingRecord]) -> None:
        with gzip.open(self.path(doc_id), "at", encoding="utf-8") as fh:
            for r in records:
                fh.write(
                    json.dumps(
                        {
                            "id": r.id,
                            "text": r.text,
                            "metadata": r.metadata,
                            "vector": [round(x, 6) for x in r.vector],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    def reset(self, doc_id: str) -> None:
        self.path(doc_id).unlink(missing_ok=True)

    def rewrite(self, doc_id: str, records: Iterable[EmbeddingRecord]) -> None:
        self.reset(doc_id)
        self.append(doc_id, records)

    def load_all(self, doc_ids: Iterable[str]) -> list[EmbeddingRecord]:
        out: list[EmbeddingRecord] = []
        for doc_id in doc_ids:
            out.extend(self.load(doc_id).values())
        return out


# --- manifest ---------------------------------------------------------------------------------


def load_manifest(settings: Settings) -> dict[str, dict[str, Any]]:
    if settings.manifest_path.exists():
        return json.loads(settings.manifest_path.read_text(encoding="utf-8"))
    return {}


def save_manifest(settings: Settings, manifest: dict[str, dict[str, Any]]) -> None:
    settings.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    settings.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def manifest_key(source: SourceDoc, settings: Settings) -> dict[str, Any]:
    """The inputs that, if changed, invalidate a document's cached embeddings."""
    return {
        "sha256": sha256_of(source.pdf_path(settings)),
        "pages": list(source.pages) if source.pages else None,
        "embedding_model": settings.embedding_model,
        "embedding_dim": settings.embedding_dim,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
    }


def is_current(entry: dict[str, Any] | None, key: dict[str, Any]) -> bool:
    return entry is not None and all(entry.get(k) == v for k, v in key.items())


# --- build -----------------------------------------------------------------------------------


def _is_rate_limit(exc: Exception) -> bool:
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


def embed_missing(
    doc_id: str,
    chunks: list[Chunk],
    embedder: Embeddings,
    cache: EmbeddingCache,
    batch_size: int = 50,
    pause_s: float = 0.5,
    max_retries: int = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Embed the chunks that are not yet in the cache. Resumable: every batch is written
    before the next one starts, so a quota error mid-way loses nothing. Returns the number
    of chunks embedded in this call."""
    existing = cache.load(doc_id)
    wanted = {c.id for c in chunks}
    stale = [rid for rid in existing if rid not in wanted]
    if stale:
        # The cleaning/chunking code changed for this document (same PDF, same params):
        # keep the vectors we can reuse, drop the ones no chunk refers to any more.
        log.info("[embed] %s: pruning %d stale cached chunks", doc_id, len(stale))
        cache.rewrite(doc_id, (r for rid, r in existing.items() if rid in wanted))
        existing = {rid: r for rid, r in existing.items() if rid in wanted}
    missing = [c for c in chunks if c.id not in existing]
    if not missing:
        log.info("[embed] %s: 0 new chunks (%d cached)", doc_id, len(existing))
        return 0
    log.info("[embed] %s: %d new chunks in batches of %d", doc_id, len(missing), batch_size)
    done = 0
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        delay = 10.0
        for attempt in range(max_retries):
            try:
                vectors = embedder.embed_documents([c.text for c in batch])
                break
            except Exception as exc:
                if not _is_rate_limit(exc) or attempt == max_retries - 1:
                    raise
                log.warning("[embed] rate limited, waiting %.0fs (attempt %d)", delay, attempt + 1)
                sleep(delay)
                delay *= 2
        cache.append(
            doc_id,
            (
                EmbeddingRecord(c.id, c.text, c.metadata, v)
                for c, v in zip(batch, vectors, strict=True)
            ),
        )
        done += len(batch)
        log.info("[embed] %s: %d/%d", doc_id, done, len(missing))
        if pause_s and start + batch_size < len(missing):
            sleep(pause_s)
    return done


@dataclass
class BuildReport:
    chunks_per_doc: dict[str, int]
    embedded_per_doc: dict[str, int]
    skipped: list[str]

    @property
    def total_chunks(self) -> int:
        return sum(self.chunks_per_doc.values())

    @property
    def total_embedded(self) -> int:
        return sum(self.embedded_per_doc.values())


def build_kb(
    settings: Settings,
    doc_embedder: Embeddings | None,
    doc_ids: list[str] | None = None,
    dry_run: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> BuildReport:
    """Ingest -> embed what is missing -> update manifest. With `dry_run` nothing is
    embedded; the report only counts chunks (used to check the quota budget)."""
    sources = [s for s in load_sources(settings) if (doc_ids is None or s.doc_id in doc_ids)]
    cache = EmbeddingCache(settings.cache_dir)
    manifest = load_manifest(settings)
    report = BuildReport({}, {}, [])

    for source in sources:
        if not source.pdf_path(settings).exists():
            log.warning(
                "[build] %s: PDF missing, run scripts/00_download_sources.py", source.doc_id
            )
            report.skipped.append(source.doc_id)
            continue
        chunks = ingest(source, settings)
        report.chunks_per_doc[source.doc_id] = len(chunks)
        if dry_run:
            continue
        if doc_embedder is None:
            raise ValueError("an embeddings client is required unless dry_run=True")
        key = manifest_key(source, settings)
        if not is_current(manifest.get(source.doc_id), key):
            if source.doc_id in manifest:
                log.info("[build] %s: inputs changed, discarding cached embeddings", source.doc_id)
            cache.reset(source.doc_id)
        n = embed_missing(
            source.doc_id, chunks, doc_embedder, cache, settings.embedding_batch_size, sleep=sleep
        )
        report.embedded_per_doc[source.doc_id] = n
        manifest[source.doc_id] = {
            **key,
            "n_chunks": len(chunks),
            "title": source.title,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    if not dry_run:
        save_manifest(settings, manifest)
    return report


# --- Chroma -------------------------------------------------------------------------------------


def _manifest_stamp(manifest: dict[str, dict[str, Any]]) -> str:
    return json.dumps({k: v.get("built_at") for k, v in sorted(manifest.items())}, sort_keys=True)


def rebuild_chroma(settings: Settings, query_embedder: Embeddings) -> Chroma:
    """Recreate the persisted collection from the cache. No embedding API calls: vectors
    are inserted through Chroma's native `add` with precomputed embeddings."""
    manifest = load_manifest(settings)
    records = EmbeddingCache(settings.cache_dir).load_all(sorted(manifest))
    if settings.chroma_dir.exists():
        shutil.rmtree(settings.chroma_dir)
    settings.chroma_dir.mkdir(parents=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    collection = client.get_or_create_collection(
        settings.collection_name, metadata={"hnsw:space": "cosine"}
    )
    for start in range(0, len(records), 500):
        batch = records[start : start + 500]
        collection.add(
            ids=[r.id for r in batch],
            embeddings=[r.vector for r in batch],
            documents=[r.text for r in batch],
            metadatas=[r.metadata for r in batch],
        )
    (settings.chroma_dir / ".built_from").write_text(_manifest_stamp(manifest), encoding="utf-8")
    log.info(
        "[chroma] rebuilt %s with %d chunks from cache",
        settings.collection_name,
        collection.count(),
    )
    return Chroma(
        client=client,
        collection_name=settings.collection_name,
        embedding_function=query_embedder,
        collection_metadata={"hnsw:space": "cosine"},
    )


def build_or_load(settings: Settings, query_embedder: Embeddings) -> Chroma:
    """Open the persisted collection if it matches the manifest, else rebuild it."""
    manifest = load_manifest(settings)
    stamp = settings.chroma_dir / ".built_from"
    if stamp.exists() and stamp.read_text(encoding="utf-8") == _manifest_stamp(manifest):
        client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        log.info("[chroma] loaded %s from %s", settings.collection_name, settings.chroma_dir)
        return Chroma(
            client=client,
            collection_name=settings.collection_name,
            embedding_function=query_embedder,
            collection_metadata={"hnsw:space": "cosine"},
        )
    return rebuild_chroma(settings, query_embedder)
