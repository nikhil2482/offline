"""The source allowlist, downloads, and hash verification.

Nothing gets fetched or ingested unless it is on the allowlist. Every file is
hashed on download, and ingest refuses any file whose hash no longer matches.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args
from urllib.parse import urlparse

import httpx
import yaml

Format = Literal["ecfr_xml", "pdf"]
Marking = Literal["public_domain", "public_release"]

MAX_BYTES = 50 * 1024 * 1024
_EXTENSIONS: dict[str, str] = {"ecfr_xml": "xml", "pdf": "pdf"}


class SourceError(Exception):
    """A source failed an allowlist, integrity, or marking check."""


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    url: str
    format: Format
    marking: Marking
    cite_url: str = ""

    @property
    def filename(self) -> str:
        return f"{self.id}.{_EXTENSIONS[self.format]}"

    def link(self, section: str, page: int | None) -> str:
        if self.cite_url:
            return self.cite_url.format(section=section)
        if page is not None:
            return f"{self.url}#page={page}"
        return self.url


@dataclass(frozen=True)
class Allowlist:
    hosts: frozenset[str]
    sources: tuple[Source, ...]

    def get(self, source_id: str) -> Source:
        for source in self.sources:
            if source.id == source_id:
                return source
        raise SourceError(f"{source_id} is not on the allowlist")


def load_allowlist(path: Path) -> Allowlist:
    raw = yaml.safe_load(path.read_text())
    hosts = frozenset(raw["allowed_hosts"])
    sources = tuple(Source(**entry) for entry in raw["sources"])

    ids = [s.id for s in sources]
    if len(ids) != len(set(ids)):
        raise SourceError("duplicate source ids in allowlist")
    for source in sources:
        if source.format not in get_args(Format):
            raise SourceError(f"{source.id}: unknown format {source.format}")
        if source.marking not in get_args(Marking):
            raise SourceError(f"{source.id}: unknown marking {source.marking}")
        check_url(source.url, hosts)
    return Allowlist(hosts, sources)


def check_url(url: str, hosts: frozenset[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SourceError(f"{url} is not https")
    if parsed.hostname not in hosts:
        raise SourceError(f"{parsed.hostname} is not an allowed host")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_lock(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    data: dict[str, dict[str, str]] = json.loads(path.read_text())
    return data


def write_lock(path: Path, lock: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


def fetch(
    source: Source,
    allowlist: Allowlist,
    raw_dir: Path,
    lock_path: Path,
    client: httpx.Client,
    *,
    update: bool = False,
) -> str:
    """Download one source and record its hash. Returns the sha256."""
    check_url(source.url, allowlist.hosts)
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / source.filename
    partial = dest.with_suffix(dest.suffix + ".part")

    received = 0
    with client.stream("GET", source.url) as response:
        response.raise_for_status()
        with partial.open("wb") as f:
            for block in response.iter_bytes():
                received += len(block)
                if received > MAX_BYTES:
                    f.close()
                    partial.unlink()
                    raise SourceError(f"{source.id} is larger than {MAX_BYTES} bytes")
                f.write(block)

    digest = sha256_file(partial)
    lock = read_lock(lock_path)
    known = lock.get(source.id)
    if known and known["sha256"] != digest and not update:
        partial.unlink()
        raise SourceError(
            f"{source.id} changed upstream. Review the new version, then rerun with --update."
        )

    partial.replace(dest)
    lock[source.id] = {
        "sha256": digest,
        "url": source.url,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    write_lock(lock_path, lock)
    return digest


def verified_path(source: Source, raw_dir: Path, lock_path: Path) -> Path:
    """Return the local file for a source after checking it against the lock file."""
    entry = read_lock(lock_path).get(source.id)
    if entry is None:
        raise SourceError(f"{source.id} is not in the lock file. Run fetch first.")
    path = raw_dir / source.filename
    if not path.exists():
        raise SourceError(f"{path} is missing")
    if sha256_file(path) != entry["sha256"]:
        raise SourceError(f"{source.id} does not match its recorded hash")
    return path
