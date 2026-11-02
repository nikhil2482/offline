"""Append only audit log. Each entry carries the hash of the one before it,
so editing or deleting a line breaks the chain and shows up in verify_chain.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def _digest(entry: dict[str, Any]) -> str:
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        ok, _ = verify_chain(path)
        if not ok:
            raise RuntimeError(f"audit log {path} failed its integrity check")
        last = self.tail(1)
        self._last_hash = last[0]["hash"] if last else GENESIS

    @property
    def path(self) -> Path:
        return self._path

    def record(self, event: str, actor: str, **data: Any) -> None:
        with self._lock:
            entry = {
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "event": event,
                "actor": actor,
                "data": data,
                "prev": self._last_hash,
            }
            entry["hash"] = _digest(entry)
            with self._path.open("a") as f:
                f.write(json.dumps(entry, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._last_hash = entry["hash"]

    def tail(self, n: int) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open() as f:
            return [json.loads(line) for line in deque(f, maxlen=n)]


def verify_chain(path: Path) -> tuple[bool, int]:
    """Return (valid, entries checked). Stops at the first broken entry."""
    if not path.exists():
        return True, 0
    prev = GENESIS
    count = 0
    with path.open() as f:
        for line in f:
            entry = json.loads(line)
            claimed = entry.pop("hash", None)
            if entry.get("prev") != prev or claimed != _digest(entry):
                return False, count
            prev = claimed
            count += 1
    return True, count
