from pathlib import Path

import httpx
import pytest

from offline import sources
from offline.sources import SourceError, fetch, load_allowlist, read_lock, verified_path

ALLOWLIST = """
allowed_hosts: [www.ecfr.gov]
sources:
  - id: far-part-13
    title: FAR Part 13
    url: https://www.ecfr.gov/api/versioner/v1/full/2026-10-01/title-48.xml?part=13
    format: ecfr_xml
    marking: public_domain
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(text)
    return path


def client(body: bytes, status: int = 200) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, content=body))
    )


def test_rejects_plain_http(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not https"):
        load_allowlist(write(tmp_path, ALLOWLIST.replace("https://", "http://")))


def test_rejects_unlisted_host(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not an allowed host"):
        load_allowlist(write(tmp_path, ALLOWLIST.replace("www.ecfr.gov/api", "evil.example/api")))


def test_rejects_duplicate_ids(tmp_path: Path) -> None:
    doubled = ALLOWLIST + ALLOWLIST.split("sources:\n")[1]
    with pytest.raises(SourceError, match="duplicate"):
        load_allowlist(write(tmp_path, doubled))


def test_fetch_records_hash_and_verifies(tmp_path: Path) -> None:
    allowlist = load_allowlist(write(tmp_path, ALLOWLIST))
    source = allowlist.get("far-part-13")
    lock = tmp_path / "lock.json"
    digest = fetch(source, allowlist, tmp_path / "raw", lock, client(b"<xml/>"))
    assert read_lock(lock)["far-part-13"]["sha256"] == digest
    assert verified_path(source, tmp_path / "raw", lock).read_bytes() == b"<xml/>"


def test_changed_upstream_needs_update(tmp_path: Path) -> None:
    allowlist = load_allowlist(write(tmp_path, ALLOWLIST))
    source = allowlist.get("far-part-13")
    lock = tmp_path / "lock.json"
    fetch(source, allowlist, tmp_path / "raw", lock, client(b"v1"))
    with pytest.raises(SourceError, match="changed upstream"):
        fetch(source, allowlist, tmp_path / "raw", lock, client(b"v2"))
    fetch(source, allowlist, tmp_path / "raw", lock, client(b"v2"), update=True)


def test_tampered_file_is_rejected(tmp_path: Path) -> None:
    allowlist = load_allowlist(write(tmp_path, ALLOWLIST))
    source = allowlist.get("far-part-13")
    lock = tmp_path / "lock.json"
    fetch(source, allowlist, tmp_path / "raw", lock, client(b"original"))
    (tmp_path / "raw" / source.filename).write_bytes(b"edited")
    with pytest.raises(SourceError, match="does not match"):
        verified_path(source, tmp_path / "raw", lock)


def test_redirect_is_refused(tmp_path: Path) -> None:
    allowlist = load_allowlist(write(tmp_path, ALLOWLIST))
    source = allowlist.get("far-part-13")
    with pytest.raises(httpx.HTTPStatusError):
        fetch(source, allowlist, tmp_path / "raw", tmp_path / "lock.json", client(b"", 302))


def test_oversized_download_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "MAX_BYTES", 4)
    allowlist = load_allowlist(write(tmp_path, ALLOWLIST))
    source = allowlist.get("far-part-13")
    with pytest.raises(SourceError, match="larger than"):
        fetch(source, allowlist, tmp_path / "raw", tmp_path / "lock.json", client(b"too big"))
