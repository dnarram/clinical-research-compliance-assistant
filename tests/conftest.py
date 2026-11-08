"""Shared fixtures. Everything here runs offline: no Gemini key, no network."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from compliance_assistant.config import Settings
from compliance_assistant.ingestion import SourceDoc

PAGE_TEXTS = [
    "ICH E9X TEST GUIDELINE\n1 INTRODUCTION\nThis guideline describes expedited reporting of "
    "serious adverse events in clinical trials. Sponsors must report to regulators.\nPage 1 of 3",
    "ICH E9X TEST GUIDELINE\n1.1 Definitions\nA serious adverse event (SAE) is any untoward "
    "medical occurrence that results in death or is life-threatening or requires hospitalisation.\n"
    "1.2 Timelines\nFatal or life-threatening unexpected ADRs must be reported within 7 calendar "
    "days; all other serious unexpected ADRs within 15 calendar days.\nPage 2 of 3",
    "ICH E9X TEST GUIDELINE\n2 RESPONSIBILITIES\nThe investigator informs the sponsor immediately. "
    "The sponsor is responsible for pharmaco-\nvigilance and for expedited reports.\nPage 3 of 3",
]


def _write_pdf(path: Path, texts: list[str]) -> None:
    """A real PDF with extractable text, so pypdf exercises the same code path as prod."""
    from pypdf import PageObject
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for text in texts:
        page = PageObject.create_blank_page(width=595, height=842)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        lines = text.split("\n")
        ops = ["BT", "/F1 11 Tf", "14 TL", "40 800 Td"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({escaped}) Tj T*")
        ops.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.add_page(page)
    with path.open("wb") as fh:
        writer.write(fh)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    kb = tmp_path / "kb"
    (kb / "raw").mkdir(parents=True)
    (kb / "embeddings").mkdir()
    return Settings(
        project_root=tmp_path,
        kb_dir=kb,
        chroma_dir=tmp_path / "chroma",
        golden_path=tmp_path / "golden.jsonl",
        chunk_size=200,
        chunk_overlap=20,
    )


@pytest.fixture
def source(settings: Settings) -> SourceDoc:
    src = SourceDoc(
        doc_id="test_e9x",
        title="ICH E9X Test Guideline",
        short_cite="ICH E9X",
        url="https://example.org/e9x.pdf",
        section_style="ich",
    )
    _write_pdf(src.pdf_path(settings), PAGE_TEXTS)
    return src
