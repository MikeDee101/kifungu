"""Parser interface.

A parser sees only the canonical text of a document and returns flat nodes with
character spans. It never touches geometry: bboxes are attached afterwards by
mapping spans onto extracted words, so a parser change can never move a box
except through the text it claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Marker:
    """A structural marker found at the start of a line."""

    kind: str
    number: str
    offset: int  # char offset of the marker in the full text
    heading: str = ""


@dataclass
class RawNode:
    kind: str
    number: str
    citation: str
    char_span: tuple[int, int]
    heading: str = ""
    parent: str | None = None
    id: str = ""
    children: list[str] = field(default_factory=list)


class Parser(Protocol):
    name: str

    def parse(self, text: str) -> list[RawNode]:
        """Return flat nodes, parents before children, spans into `text`."""
        ...
