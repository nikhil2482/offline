"""Command line tools: fetch, ingest, add-user, verify-audit, eval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

from offline import evals
from offline.audit import AuditLog, verify_chain
from offline.auth import Role, add_user
from offline.chunking import chunk_sections
from offline.config import Settings
from offline.ingest import parse
from offline.services import build
from offline.sources import SourceError, fetch, load_allowlist, verified_path

_BATCH = 32


def cmd_fetch(settings: Settings, args: argparse.Namespace) -> None:
    allowlist = load_allowlist(settings.sources_file)
    targets = [allowlist.get(args.only)] if args.only else allowlist.sources
    headers = {"User-Agent": "offline/0.1 (public regulation research)"}
    with httpx.Client(timeout=60, follow_redirects=False, headers=headers) as client:
        for source in targets:
            digest = fetch(
                source, allowlist, settings.raw_dir, settings.lock_file, client, update=args.update
            )
            print(f"fetched {source.id} sha256={digest}")


def cmd_ingest(settings: Settings, args: argparse.Namespace) -> None:
    services = build(settings)
    targets = [services.allowlist.get(args.only)] if args.only else services.allowlist.sources
    for source in targets:
        path = verified_path(source, settings.raw_dir, settings.lock_file)
        chunks = chunk_sections(parse(source, path))
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), _BATCH):
            batch = [c.embedding_text() for c in chunks[start : start + _BATCH]]
            vectors.extend(services.embedder.embed(batch, "document"))
        services.store.replace_source(source.id, chunks, vectors)
        services.audit.record("ingest", "cli", source=source.id, chunks=len(chunks))
        print(f"ingested {source.id}: {len(chunks)} chunks")


def cmd_add_user(settings: Settings, args: argparse.Namespace) -> None:
    token = add_user(settings.tokens_file, args.name, Role(args.role))
    AuditLog(settings.audit_file).record("user_added", "cli", name=args.name, role=args.role)
    print(f"Created {args.name} ({args.role}). This token is shown once. Store it safely:\n{token}")


def cmd_verify_audit(settings: Settings, args: argparse.Namespace) -> None:
    valid, checked = verify_chain(settings.audit_file)
    print(f"{'valid' if valid else 'BROKEN'} after {checked} entries")
    if not valid:
        sys.exit(1)


def cmd_eval(settings: Settings, args: argparse.Namespace) -> None:
    services = build(settings)
    results = evals.run(services.answerer, evals.load_cases(args.file))
    for r in results:
        mark = "pass" if r.passed else "FAIL"
        print(f"{mark}  {r.status:<10} {','.join(r.cited) or '':<16} {r.q}")
    evals.write(results, services.answerer.model_name, args.out)
    print(evals.summarize(results))


def main() -> None:
    parser = argparse.ArgumentParser(prog="offline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", help="download allowlisted sources and record their hashes")
    p.add_argument("--only", help="fetch one source id")
    p.add_argument("--update", action="store_true", help="accept a changed upstream file")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("ingest", help="parse, chunk and embed verified sources")
    p.add_argument("--only", help="ingest one source id")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("add-user", help="create a user and print their token once")
    p.add_argument("name")
    p.add_argument("role", choices=[r.value for r in Role])
    p.set_defaults(func=cmd_add_user)

    p = sub.add_parser("verify-audit", help="check the audit log hash chain")
    p.set_defaults(func=cmd_verify_audit)

    p = sub.add_parser("eval", help="run the question set and write results")
    p.add_argument("--file", type=Path, default=Path("evals/questions.yaml"))
    p.add_argument("--out", type=Path, default=Path("evals/results.json"))
    p.set_defaults(func=cmd_eval)

    args = parser.parse_args()
    try:
        args.func(Settings(), args)
    except (SourceError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
