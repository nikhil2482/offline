"""Score the system on a fixed question set.

An answerable question passes when it is answered and at least one citation falls
in the expected part. An unanswerable question passes when the system declines.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import yaml

from offline.answer import Answerer


@dataclass(frozen=True)
class Case:
    q: str
    expect: Literal["answered", "not_found"]
    section_prefix: str = ""


@dataclass(frozen=True)
class Result:
    q: str
    expect: str
    status: str
    cited: list[str]
    passed: bool


def load_cases(path: Path) -> list[Case]:
    return [Case(**c) for c in yaml.safe_load(path.read_text())["questions"]]


def run(answerer: Answerer, cases: list[Case]) -> list[Result]:
    results = []
    for case in cases:
        answer = answerer.ask(case.q)
        cited = [c.section for c in answer.citations]
        if case.expect == "answered":
            passed = answer.status == "answered" and any(
                s.startswith(case.section_prefix) for s in cited
            )
        else:
            passed = answer.status == "not_found"
        results.append(Result(case.q, case.expect, answer.status, cited, passed))
    return results


def summarize(results: list[Result]) -> dict[str, float | int]:
    answerable = [r for r in results if r.expect == "answered"]
    unanswerable = [r for r in results if r.expect == "not_found"]
    return {
        "questions": len(results),
        "citation_accuracy": _rate(answerable),
        "refusal_accuracy": _rate(unanswerable),
        "blocked": sum(r.status == "blocked" for r in results),
    }


def write(results: list[Result], model: str, path: Path) -> None:
    payload = {
        "model": model,
        "summary": summarize(results),
        "results": [asdict(r) for r in results],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _rate(results: list[Result]) -> float:
    return round(sum(r.passed for r in results) / len(results), 3) if results else 0.0
