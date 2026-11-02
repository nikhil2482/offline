"""Wire settings into the objects the API and CLI use."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from offline.answer import Answerer
from offline.audit import AuditLog
from offline.auth import UserStore
from offline.config import Mode, Settings
from offline.models import AnthropicChat, ChatModel, OllamaChat, OllamaEmbedder
from offline.ratelimit import RateLimiter
from offline.sources import Allowlist, load_allowlist
from offline.store import PgVectorStore, Store


@dataclass(frozen=True)
class Services:
    settings: Settings
    allowlist: Allowlist
    embedder: OllamaEmbedder
    store: Store
    answerer: Answerer
    audit: AuditLog
    users: UserStore
    limiter: RateLimiter


def build(settings: Settings) -> Services:
    allowlist = load_allowlist(settings.sources_file)
    local = httpx.Client(base_url=settings.ollama_url, timeout=120)
    embedder = OllamaEmbedder(local, settings.embed_model)
    store = PgVectorStore(settings.database_url, settings.embed_dim)

    model: ChatModel
    if settings.mode is Mode.CLOUD:
        model = AnthropicChat(
            httpx.Client(timeout=60), settings.cloud_model, settings.anthropic_api_key
        )
    else:
        model = OllamaChat(local, settings.chat_model)

    def link(source_id: str, section: str, page: int | None) -> str:
        return allowlist.get(source_id).link(section, page)

    return Services(
        settings=settings,
        allowlist=allowlist,
        embedder=embedder,
        store=store,
        answerer=Answerer(embedder, store, model, link, settings.top_k, settings.min_score),
        audit=AuditLog(settings.audit_file),
        users=UserStore(settings.tokens_file),
        limiter=RateLimiter(settings.rate_limit_per_minute),
    )
