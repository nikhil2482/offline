"""HTTP API. Every request is authenticated, rate limited, and written to the audit log."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from offline.answer import Answer, Answerer, Status
from offline.audit import AuditLog, sha256_text, verify_chain
from offline.auth import Role, User, UserStore
from offline.ratelimit import RateLimiter

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1000)


class CitationOut(BaseModel):
    label: str
    source_id: str
    section: str
    heading: str
    page: int | None
    excerpt: str
    url: str


class AnswerOut(BaseModel):
    status: Status
    text: str
    citations: list[CitationOut]

    @classmethod
    def of(cls, answer: Answer) -> "AnswerOut":
        return cls(
            status=answer.status,
            text=answer.text,
            citations=[CitationOut(**vars(c)) for c in answer.citations],
        )


def create_app(
    answerer: Answerer,
    audit: AuditLog,
    users: UserStore,
    limiter: RateLimiter,
    mode: str,
) -> FastAPI:
    app = FastAPI(title="Offline", docs_url=None, redoc_url=None, openapi_url=None)
    bearer = HTTPBearer(auto_error=False)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(_SECURITY_HEADERS)
        return response

    def current_user(
        request: Request,
        creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> User:
        user = users.lookup(creds.credentials) if creds else None
        if user is None:
            client = request.client.host if request.client else "unknown"
            audit.record("auth_failed", "unknown", path=request.url.path, client=client)
            raise HTTPException(401, "missing or invalid token")
        return user

    def require(*roles: Role) -> Callable[[User], User]:
        def check(user: Annotated[User, Depends(current_user)]) -> User:
            if user.role not in roles:
                audit.record("access_denied", user.name, role=user.role.value)
                raise HTTPException(403, "your role cannot do this")
            return user

        return check

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": mode}

    @app.post("/api/ask")
    def ask(
        body: AskRequest, user: Annotated[User, Depends(require(Role.ANALYST, Role.ADMIN))]
    ) -> AnswerOut:
        if not limiter.allow(user.name):
            audit.record("rate_limited", user.name)
            raise HTTPException(429, "too many questions. Wait a minute and try again.")
        try:
            answer = answerer.ask(body.question.strip())
        except httpx.HTTPError as exc:
            audit.record("model_error", user.name, error=type(exc).__name__)
            raise HTTPException(502, "the model service is unavailable") from exc

        audit.record(
            "ask",
            user.name,
            question=body.question,
            status=answer.status,
            reason=answer.reason,
            retrieved=answer.retrieved,
            cited=[f"{c.source_id}:{c.section}" for c in answer.citations],
            answer_sha256=sha256_text(answer.text),
            model=answerer.model_name,
        )
        return AnswerOut.of(answer)

    @app.get("/api/audit")
    def audit_entries(
        user: Annotated[User, Depends(require(Role.ADMIN))],
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ) -> dict[str, Any]:
        audit.record("audit_viewed", user.name, limit=limit)
        valid, checked = verify_chain(audit.path)
        return {"chain_valid": valid, "entries_checked": checked, "entries": audit.tail(limit)}

    return app
