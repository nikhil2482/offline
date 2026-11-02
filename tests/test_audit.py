import json
from pathlib import Path

import pytest

from offline.audit import AuditLog, verify_chain


def test_chain_is_valid_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    AuditLog(path).record("ask", "alice", question="q1")
    AuditLog(path).record("ask", "bob", question="q2")
    assert verify_chain(path) == (True, 2)


def test_edited_entry_breaks_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.record("ask", "alice", question="original")
    log.record("ask", "alice", question="second")
    lines = path.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["data"]["question"] = "edited"
    lines[0] = json.dumps(entry, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    assert verify_chain(path) == (False, 0)
    with pytest.raises(RuntimeError, match="integrity"):
        AuditLog(path)


def test_deleted_entry_breaks_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for n in range(3):
        log.record("ask", "alice", n=n)
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert verify_chain(path) == (False, 1)
