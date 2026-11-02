"""Parse verified source files into citable sections."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree
from pypdf import PdfReader

from offline.sources import Source, SourceError

_RELEASE = re.compile(r"approved\s+for\s+public\s+release", re.IGNORECASE)
_SPACES = re.compile(r"[ \t\r\f\v]+")


@dataclass(frozen=True)
class Section:
    source_id: str
    section: str
    heading: str
    text: str
    page: int | None = None


def parse(source: Source, path: Path) -> list[Section]:
    data = path.read_bytes()
    if source.format == "ecfr_xml":
        sections = parse_ecfr(source.id, data)
    else:
        sections = parse_pdf(source.id, data)
    if not sections:
        raise SourceError(f"{source.id}: no sections found")
    check_marking(source, sections)
    return sections


def check_marking(source: Source, sections: list[Section]) -> None:
    """PDFs marked public_release must say so on one of their first pages."""
    if source.marking != "public_release":
        return
    if not any(_RELEASE.search(s.text) for s in sections[:5]):
        raise SourceError(f"{source.id}: no public release statement found. Refusing to ingest.")


def parse_ecfr(source_id: str, data: bytes) -> list[Section]:
    """Read sections from eCFR XML, where each section is a DIV8 element with TYPE=SECTION."""
    root = ElementTree.fromstring(data)
    sections: list[Section] = []
    for div in root.iter("DIV8"):
        if div.get("TYPE") != "SECTION":
            continue
        number = (div.get("N") or "").strip()
        head = div.find("HEAD")
        heading = _clean("".join(head.itertext())) if head is not None else ""
        heading = heading.removeprefix("§").strip().removeprefix(number).strip()
        paragraphs = [_clean("".join(child.itertext())) for child in div if child.tag != "HEAD"]
        text = "\n\n".join(p for p in paragraphs if p)
        if number and text:
            sections.append(Section(source_id, number, heading, text))
    return sections


def parse_pdf(source_id: str, data: bytes) -> list[Section]:
    reader = PdfReader(io.BytesIO(data))
    sections: list[Section] = []
    for number, page in enumerate(reader.pages, start=1):
        lines = (_clean(line) for line in (page.extract_text() or "").splitlines())
        text = "\n".join(line for line in lines if line)
        if text:
            sections.append(Section(source_id, f"p. {number}", "", text, page=number))
    return sections


def _clean(text: str) -> str:
    return _SPACES.sub(" ", text).replace("\n", " ").strip()
