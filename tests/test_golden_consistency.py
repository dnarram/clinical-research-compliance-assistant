"""The golden set must point at documents and sections that actually exist in the cache.

Runs against the committed data files (no API); skipped if they are absent.
"""

from __future__ import annotations

import pytest

from compliance_assistant.config import load_settings
from compliance_assistant.evaluation import load_golden
from compliance_assistant.ingestion import load_sources
from compliance_assistant.vectorstore import EmbeddingCache, load_manifest

settings = load_settings()
pytestmark = pytest.mark.skipif(
    not settings.golden_path.exists() or not settings.manifest_path.exists(),
    reason="golden set or embedding cache not present",
)


def test_golden_items_reference_real_documents_and_sections() -> None:
    items = load_golden(settings.golden_path)
    doc_ids = {s.doc_id for s in load_sources(settings)}
    sections_by_doc: dict[str, set[str]] = {}
    for rec in EmbeddingCache(settings.cache_dir).load_all(sorted(load_manifest(settings))):
        sections_by_doc.setdefault(rec.metadata["doc_id"], set()).add(str(rec.metadata["section"]))

    assert len({i.id for i in items}) == len(items), "duplicate ids"
    assert len(items) >= 12
    for item in items:
        assert set(item.questions) == {"en", "es"}, f"{item.id}: both languages required"
        for doc in item.expected_doc_ids:
            assert doc in doc_ids, f"{item.id}: unknown doc_id {doc}"
        if item.type == "in_domain":
            assert item.expected_doc_ids, f"{item.id}: in_domain needs expected_doc_ids"
            for section in item.expected_sections:
                assert any(
                    section in sections_by_doc.get(d, set()) for d in item.expected_doc_ids
                ), f"{item.id}: section {section!r} not found in {item.expected_doc_ids}"
        else:
            assert not item.expected_doc_ids, f"{item.id}: {item.type} items carry no expected docs"
