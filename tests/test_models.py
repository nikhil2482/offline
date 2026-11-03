"""Cloud clients send the right request shape and parse the reply."""

import json

import httpx
import pytest

from offline.models import AnthropicChat, OpenAIChat


def _client(reply: dict[str, object], seen: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=reply)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_request_and_reply() -> None:
    seen: list[httpx.Request] = []
    reply = {"choices": [{"message": {"content": "ok"}}]}
    model = OpenAIChat(_client(reply, seen), "gpt-test", "key123", "low")
    assert model.complete("sys", "hi") == "ok"
    body = json.loads(seen[0].content)
    assert seen[0].headers["authorization"] == "Bearer key123"
    assert body["model"] == "gpt-test"
    assert body["reasoning_effort"] == "low"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert "temperature" not in body
    assert model.name == "openai/gpt-test"


def test_anthropic_request_and_reply() -> None:
    seen: list[httpx.Request] = []
    reply = {"content": [{"type": "text", "text": "ok"}]}
    model = AnthropicChat(_client(reply, seen), "claude-test", "key456")
    assert model.complete("sys", "hi") == "ok"
    assert seen[0].headers["x-api-key"] == "key456"
    assert json.loads(seen[0].content)["system"] == "sys"


@pytest.mark.parametrize("cls", [OpenAIChat, AnthropicChat])
def test_missing_key_is_refused(cls: type) -> None:
    args = ("m", "", "low") if cls is OpenAIChat else ("m", "")
    with pytest.raises(ValueError, match="API_KEY"):
        cls(httpx.Client(), *args)
