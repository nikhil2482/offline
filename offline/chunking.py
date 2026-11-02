"""Split sections into chunks small enough to retrieve and cite."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from offline.ingest import Section

MAX_CHARS = 1500


@dataclass(frozen=True)
class Chunk:
    id: str
    source_id: str
    section: str
    heading: str
    text: str
    page: int | None = None

    def embedding_text(self) -> str:
        return f"{self.section} {self.heading}\n{self.text}".strip()


def chunk_sections(sections: Iterable[Section], max_chars: int = MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in sections:
        for n, text in enumerate(_pack(section.text, max_chars)):
            chunks.append(
                Chunk(
                    id=f"{section.source_id}:{section.section}:{n}",
                    source_id=section.source_id,
                    section=section.section,
                    heading=section.heading,
                    text=text,
                    page=section.page,
                )
            )
    return chunks


def _pack(text: str, max_chars: int) -> Iterator[str]:
    """Group whole paragraphs into chunks, splitting only paragraphs that are too long alone."""
    current: list[str] = []
    size = 0
    for paragraph in _pieces(text, max_chars):
        if current and size + len(paragraph) > max_chars:
            yield "\n\n".join(current)
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        yield "\n\n".join(current)


def _pieces(text: str, max_chars: int) -> Iterator[str]:
    for paragraph in (p.strip() for p in text.split("\n\n")):
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            yield paragraph
            continue
        words: list[str] = []
        size = 0
        for word in paragraph.split():
            if words and size + len(word) > max_chars:
                yield " ".join(words)
                words, size = [], 0
            words.append(word)
            size += len(word) + 1
        if words:
            yield " ".join(words)
