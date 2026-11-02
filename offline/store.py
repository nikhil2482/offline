"""Vector storage. Postgres with pgvector in production, an in-memory store for tests."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import psycopg
from psycopg import sql

from offline.chunking import Chunk


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Store(Protocol):
    def replace_source(
        self, source_id: str, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]
    ) -> None: ...

    def search(self, vector: Sequence[float], k: int) -> list[Hit]: ...


class MemoryStore:
    def __init__(self) -> None:
        self._rows: list[tuple[Chunk, Sequence[float]]] = []

    def replace_source(
        self, source_id: str, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]
    ) -> None:
        self._rows = [row for row in self._rows if row[0].source_id != source_id]
        self._rows.extend(zip(chunks, vectors, strict=True))

    def search(self, vector: Sequence[float], k: int) -> list[Hit]:
        scored = [Hit(chunk, _cosine(vector, v)) for chunk, v in self._rows]
        return sorted(scored, key=lambda h: h.score, reverse=True)[:k]


class PgVectorStore:
    def __init__(self, url: str, dim: int) -> None:
        self._dim = dim
        self._conn = psycopg.connect(url, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._conn.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id text PRIMARY KEY,
                    source_id text NOT NULL,
                    section text NOT NULL,
                    heading text NOT NULL,
                    page integer,
                    text text NOT NULL,
                    embedding vector({dim}) NOT NULL
                )
                """
            ).format(dim=sql.Literal(dim))
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_idx "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        )
        row = self._conn.execute(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        ).fetchone()
        if row and row[0] != dim:
            raise ValueError(
                f"the chunks table stores {row[0]} dimensions but OFFLINE_EMBED_DIM is {dim}. "
                "Drop the table and ingest again after changing embedding models."
            )

    def replace_source(
        self, source_id: str, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]
    ) -> None:
        rows = [
            (c.id, c.source_id, c.section, c.heading, c.page, c.text, self._literal(v))
            for c, v in zip(chunks, vectors, strict=True)
        ]
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE source_id = %s", (source_id,))
            cur.executemany(
                "INSERT INTO chunks (id, source_id, section, heading, page, text, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s::vector)",
                rows,
            )

    def search(self, vector: Sequence[float], k: int) -> list[Hit]:
        literal = self._literal(vector)
        cur = self._conn.execute(
            "SELECT id, source_id, section, heading, text, page, "
            "1 - (embedding <=> %s::vector) AS score "
            "FROM chunks ORDER BY embedding <=> %s::vector LIMIT %s",
            (literal, literal, k),
        )
        return [
            Hit(Chunk(row[0], row[1], row[2], row[3], row[4], row[5]), float(row[6]))
            for row in cur.fetchall()
        ]

    def _literal(self, vector: Sequence[float]) -> str:
        if len(vector) != self._dim:
            raise ValueError(f"expected {self._dim} dimensions, got {len(vector)}")
        return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
