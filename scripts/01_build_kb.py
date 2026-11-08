#!/usr/bin/env python
"""Build the knowledge base: PDFs -> chunks -> Gemini embeddings (cached) -> ChromaDB.

    uv run scripts/01_build_kb.py --dry-run          # chunk counts only; no API calls
    uv run scripts/01_build_kb.py --doc-id ich_e2a   # start small (brief's advice)
    uv run scripts/01_build_kb.py                    # embed whatever is not cached yet
    uv run scripts/01_build_kb.py --rebuild-only     # Chroma from the committed cache, no API calls

The build is idempotent: a second run embeds nothing unless a PDF, the embedding model
or the chunking parameters changed (see data/kb/manifest.json).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compliance_assistant.config import load_api_keys, load_settings
from compliance_assistant.vectorstore import (
    TASK_DOCUMENT,
    build_kb,
    get_embeddings,
    get_query_embeddings,
    rebuild_chroma,
)

# Reported free-tier figures for Gemini embeddings; the authoritative numbers are on the
# AI Studio quota page for the project. Used only to warn before a build.
FREE_TIER_EMBED_RPD = 1000
FREE_TIER_EMBED_RPM = 100


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--doc-id", action="append", help="limit to these doc_ids (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="count chunks, embed nothing")
    parser.add_argument(
        "--rebuild-only", action="store_true", help="only rebuild Chroma from the cache"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    settings = load_settings()

    if args.rebuild_only:
        api_key = load_api_keys()  # the query embedder needs it later, not for the rebuild itself
        store = rebuild_chroma(settings, get_query_embeddings(settings, api_key))
        print(
            f"Chroma collection '{settings.collection_name}' rebuilt: {store._collection.count()} chunks"
        )
        return 0

    if args.dry_run:
        report = build_kb(settings, None, doc_ids=args.doc_id, dry_run=True)
        print("Estimated chunks per document (no API calls made):")
        for doc_id, n in report.chunks_per_doc.items():
            print(f"  {doc_id:<22} {n:>5}")
        batches = -(-report.total_chunks // settings.embedding_batch_size)
        print(
            f"  {'TOTAL':<22} {report.total_chunks:>5}  -> {batches} embedding requests of {settings.embedding_batch_size}"
        )
        print(
            f"Free-tier budget (reported): ~{FREE_TIER_EMBED_RPD} requests/day, ~{FREE_TIER_EMBED_RPM}/min. "
            f"This build needs {batches} requests."
        )
        if report.skipped:
            print(f"Skipped (PDF missing): {', '.join(report.skipped)}")
        return 0

    api_key = load_api_keys()
    print(
        f"Using embedding model {settings.embedding_model} (dim {settings.embedding_dim}); {len(api_key)} key(s)"
    )
    doc_embedder = get_embeddings(settings, api_key, TASK_DOCUMENT)
    report = build_kb(settings, doc_embedder, doc_ids=args.doc_id)
    print(f"Embedded {report.total_embedded} new chunks ({report.total_chunks} total in scope).")
    store = rebuild_chroma(settings, get_query_embeddings(settings, api_key))
    print(
        f"Chroma collection '{settings.collection_name}' now holds {store._collection.count()} chunks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
