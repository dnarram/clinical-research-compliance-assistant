from compliance_assistant.config import Settings
from compliance_assistant.ingestion import (
    Page,
    SourceDoc,
    chunk_id,
    clean_pages,
    clean_text,
    detect_sections,
    find_repeated_lines,
    ingest,
    load_pdf,
)


def test_load_pdf_keeps_one_based_page_numbers(settings: Settings, source: SourceDoc) -> None:
    pages = load_pdf(source.pdf_path(settings), source.doc_id)
    assert [p.page for p in pages] == [1, 2, 3]
    assert "expedited reporting" in pages[0].text


def test_load_pdf_page_range(settings: Settings, source: SourceDoc) -> None:
    pages = load_pdf(source.pdf_path(settings), source.doc_id, pages=(2, 3))
    assert [p.page for p in pages] == [2, 3]


def test_repeated_header_and_page_numbers_are_removed() -> None:
    pages = [
        Page("d", i, f"RUNNING HEADER\nBody text {i} that is unique.\nPage {i} of 4")
        for i in range(1, 5)
    ]
    repeated = find_repeated_lines(pages)
    assert "running header" in repeated
    cleaned = clean_pages(pages)
    assert all("RUNNING HEADER" not in p.text for p in cleaned)
    assert all("Page" not in p.text for p in cleaned)
    assert "Body text 2 that is unique." in cleaned[1].text


def test_short_documents_keep_all_lines() -> None:
    pages = [Page("d", 1, "Title\nBody"), Page("d", 2, "Title\nMore")]
    assert find_repeated_lines(pages) == set()


def test_hyphenation_and_whitespace() -> None:
    assert clean_text("pharmaco-\nvigilance   is   key") == "pharmacovigilance is key"


def test_generated_pdf_artefacts_are_repaired() -> None:
    raw = "P\nREAMBLE\n1.\nT\nhe WMA has developed\nhe WMA has developed\n3.16 Data ........... 39\niii"
    cleaned = clean_text(raw)
    assert cleaned.startswith("PREAMBLE\n1.\nThe WMA has developed")
    assert cleaned.count("he WMA has developed") == 1
    assert "3.16" not in cleaned and "iii" not in cleaned


def test_ich_sections_carry_forward() -> None:
    runs = detect_sections("1.2 Timelines\nSeven days.\nMore text.", "ich", carry=None)
    assert runs[0][0] == "1.2"
    runs = detect_sections("continuation text with 7 days", "ich", carry="1.2")
    assert runs == [("1.2", "continuation text with 7 days")]


def test_load_html_recovers_paragraph_numbers(tmp_path) -> None:
    from compliance_assistant.ingestion import load_html

    html = """<html><head><script>x()</script></head><body>
    <nav><a>Home</a></nav>
    <h1 class="page-header">WMA Declaration of Helsinki - Ethical Principles</h1>
    <p>Adopted by the 18th WMA General Assembly, June 1964</p>
    <h3>PREAMBLE</h3>
    <ol start="1"><li>The World Medical Association (WMA) has developed the Declaration.</li></ol>
    <ol start="2"><li>The Declaration is intended to be read as a whole.</li></ol>
    <h3>GENERAL PRINCIPLES</h3>
    <ol start="3"><li>The WMA Declaration of Geneva binds the physician.</li></ol>
    <p>Read more</p><p>Cookie Policy</p></body></html>"""
    path = tmp_path / "doh.html"
    path.write_text(html, encoding="utf-8")
    pages = load_html(path, "doh")
    assert len(pages) == 1 and pages[0].page == 1
    text = pages[0].text
    assert "1. The World Medical Association" in text
    assert "3. The WMA Declaration of Geneva" in text
    assert "Read more" not in text and "Home" not in text and "x()" not in text
    runs = detect_sections(text, "numbered_paragraphs", None)
    assert [r[0] for r in runs if r[0]] == ["1", "2", "3"]


def test_numbered_paragraph_sections() -> None:
    runs = detect_sections(
        "12. Medical research must conform.\n13. Groups.", "numbered_paragraphs", None
    )
    assert [r[0] for r in runs] == ["12", "13"]


def test_ingest_produces_chunks_with_citation_metadata(
    settings: Settings, source: SourceDoc
) -> None:
    chunks = ingest(source, settings)
    assert chunks, "expected at least one chunk"
    meta = chunks[0].metadata
    assert meta["doc_id"] == "test_e9x"
    assert meta["short_cite"] == "ICH E9X"
    assert meta["page"] == 1
    assert meta["section"] == "1"
    assert all(isinstance(v, str | int) for v in meta.values()), (
        "Chroma only accepts scalar metadata"
    )
    timelines = [c for c in chunks if "7 calendar" in c.text]
    assert timelines and timelines[0].metadata["section"] == "1.2"
    assert all("ICH E9X TEST GUIDELINE" not in c.text for c in chunks), "running header leaked"


def test_chunk_ids_are_deterministic(settings: Settings, source: SourceDoc) -> None:
    first = [c.id for c in ingest(source, settings)]
    second = [c.id for c in ingest(source, settings)]
    assert first == second
    assert len(set(first)) == len(first)
    assert chunk_id("d", 3, 0, "x") == chunk_id("d", 3, 0, "x")
    assert chunk_id("d", 3, 0, "x") != chunk_id("d", 3, 0, "y")
