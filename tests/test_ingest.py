from pathlib import Path

import pytest

from offline.chunking import chunk_sections
from offline.ingest import Section, check_marking, parse_ecfr
from offline.sources import Source, SourceError

FIXTURE = Path(__file__).parent / "fixtures" / "ecfr_sample.xml"


def test_parses_only_sections() -> None:
    sections = parse_ecfr("sample", FIXTURE.read_bytes())
    assert [s.section for s in sections] == ["99.001", "99.002"]
    assert sections[0].heading == "Definitions."
    assert "widget means a test item" in sections[0].text
    assert sections[0].text.count("\n\n") == 1


def test_rejects_xml_entity_expansion() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    with pytest.raises(Exception, match="Entit"):
        parse_ecfr("bomb", bomb)


def test_public_release_statement_required() -> None:
    source = Source("pub", "Pub", "https://example.host/x.pdf", "pdf", "public_release")
    unmarked = [Section("pub", "p. 1", "", "Handbook cover page")]
    with pytest.raises(SourceError, match="public release"):
        check_marking(source, unmarked)
    marked = [Section("pub", "p. 1", "", "Approved for public release.")]
    check_marking(source, marked)


def test_chunks_respect_size_and_ids_are_unique() -> None:
    long = Section("s", "1.1", "Long", "\n\n".join(["word " * 100] * 10))
    chunks = chunk_sections([long], max_chars=1200)
    assert all(len(c.text) <= 1200 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks) > 1


def test_oversized_paragraph_is_split() -> None:
    huge = Section("s", "1.2", "", "x " * 2000)
    assert all(len(c.text) <= 500 for c in chunk_sections([huge], max_chars=500))
