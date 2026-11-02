from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from offline.chunking import Chunk


@dataclass
class FakeEmbedder:
    """Maps known texts to fixed vectors. Unknown text gets an orthogonal vector."""

    vectors: dict[str, list[float]] = field(default_factory=dict)

    def embed(self, texts: Sequence[str], kind: str) -> list[list[float]]:
        return [self.vectors.get(t, [0.0, 0.0, 1.0]) for t in texts]


@dataclass
class FakeModel:
    reply: str = ""
    name: str = "fake"
    calls: list[str] = field(default_factory=list)

    def complete(self, system: str, prompt: str) -> str:
        self.calls.append(prompt)
        return self.reply


def make_chunk(section: str, text: str, source_id: str = "far-part-13") -> Chunk:
    return Chunk(f"{source_id}:{section}:0", source_id, section, "Policy.", text)


@pytest.fixture
def chunk_a() -> Chunk:
    return make_chunk("13.003", "Buyers shall use simplified acquisition procedures.")


@pytest.fixture
def chunk_b() -> Chunk:
    return make_chunk("13.106", "Contracting officers may solicit orally.")
