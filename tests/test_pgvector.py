"""Runs only when OFFLINE_TEST_DATABASE_URL points at a Postgres with pgvector."""

import os

import pytest

from offline.store import PgVectorStore
from tests.conftest import make_chunk

URL = os.environ.get("OFFLINE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="OFFLINE_TEST_DATABASE_URL not set")


def test_replace_and_search() -> None:
    assert URL
    store = PgVectorStore(URL, 3)
    a = make_chunk("13.003", "alpha", source_id="test-a")
    b = make_chunk("13.106", "bravo", source_id="test-a")
    store.replace_source("test-a", [a, b], [[1, 0, 0], [0, 1, 0]])
    store.replace_source("test-a", [a, b], [[1, 0, 0], [0, 1, 0]])

    hits = store.search([0.9, 0.1, 0], 2)
    assert [h.chunk.section for h in hits] == ["13.003", "13.106"]
    assert hits[0].score > hits[1].score


def test_wrong_dimension_is_rejected() -> None:
    assert URL
    with pytest.raises(ValueError, match="dimensions"):
        PgVectorStore(URL, 3).search([1.0, 0.0], 1)
