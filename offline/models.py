"""Clients for the embedding model and the chat model.

Embeddings always run locally through Ollama, so source text is never sent out to
be embedded. The chat model is local in offline mode and a cloud API in cloud mode.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Literal, Protocol

import httpx

Kind = Literal["document", "query"]


class Embedder(Protocol):
    def embed(self, texts: Sequence[str], kind: Kind) -> list[list[float]]: ...


class ChatModel(Protocol):
    name: str

    def complete(self, system: str, prompt: str) -> str: ...


class OllamaEmbedder:
    # nomic-embed-text was trained with these task prefixes.
    _PREFIX: ClassVar[dict[Kind, str]] = {
        "document": "search_document: ",
        "query": "search_query: ",
    }

    def __init__(self, client: httpx.Client, model: str) -> None:
        self._client = client
        self._model = model

    def embed(self, texts: Sequence[str], kind: Kind) -> list[list[float]]:
        prefix = self._PREFIX[kind]
        response = self._client.post(
            "/api/embed", json={"model": self._model, "input": [prefix + t for t in texts]}
        )
        response.raise_for_status()
        vectors: list[list[float]] = response.json()["embeddings"]
        return vectors


class OllamaChat:
    def __init__(self, client: httpx.Client, model: str) -> None:
        self._client = client
        self.name = f"ollama/{model}"
        self._model = model

    def complete(self, system: str, prompt: str) -> str:
        response = self._client.post(
            "/api/chat",
            json={
                "model": self._model,
                "stream": False,
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        return str(response.json()["message"]["content"])


class AnthropicChat:
    _URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, client: httpx.Client, model: str, api_key: str) -> None:
        if not api_key:
            raise ValueError("cloud mode needs OFFLINE_ANTHROPIC_API_KEY")
        self._client = client
        self._api_key = api_key
        self._model = model
        self.name = f"anthropic/{model}"

    def complete(self, system: str, prompt: str) -> str:
        response = self._client.post(
            self._URL,
            headers={"x-api-key": self._api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": self._model,
                "max_tokens": 1024,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        blocks = response.json()["content"]
        return "".join(b["text"] for b in blocks if b.get("type") == "text")


class OpenAIChat:
    _URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, client: httpx.Client, model: str, api_key: str, effort: str) -> None:
        if not api_key:
            raise ValueError("cloud mode needs OFFLINE_OPENAI_API_KEY")
        self._client = client
        self._api_key = api_key
        self._model = model
        self._effort = effort
        self.name = f"openai/{model}"

    def complete(self, system: str, prompt: str) -> str:
        response = self._client.post(
            self._URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "reasoning_effort": self._effort,
                "max_completion_tokens": 4000,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"] or "")
