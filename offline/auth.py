"""Bearer token users with roles. Only token hashes are stored."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

_NAME = re.compile(r"^[a-z0-9_.]{1,32}$")


class Role(StrEnum):
    ANALYST = "analyst"
    ADMIN = "admin"


@dataclass(frozen=True)
class User:
    name: str
    role: Role


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class UserStore:
    """Reloads the tokens file when it changes, so new users work without a restart."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._mtime = -1.0
        self._users: dict[str, User] = {}

    def lookup(self, token: str) -> User | None:
        self._reload()
        return self._users.get(hash_token(token))

    def _reload(self) -> None:
        mtime = self._path.stat().st_mtime if self._path.exists() else 0.0
        if mtime == self._mtime:
            return
        raw: dict[str, dict[str, str]] = json.loads(self._path.read_text()) if mtime else {}
        self._users = {h: User(u["name"], Role(u["role"])) for h, u in raw.items()}
        self._mtime = mtime


def add_user(path: Path, name: str, role: Role) -> str:
    """Create a user and return their token. The token is shown once and never stored."""
    if not _NAME.match(name):
        raise ValueError("names use lowercase letters, digits, dots and underscores, up to 32")
    raw: dict[str, dict[str, str]] = json.loads(path.read_text()) if path.exists() else {}
    if any(u["name"] == name for u in raw.values()):
        raise ValueError(f"user {name} already exists")
    token = secrets.token_urlsafe(32)
    raw[hash_token(token)] = {"name": name, "role": role.value}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2) + "\n")
    os.chmod(path, 0o600)
    return token
