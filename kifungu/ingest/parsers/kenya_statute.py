"""Structure detection for Kenyan statutes (spec §3.1).

The layout convention is stable, so this is regex-driven and deliberately
confined to one swappable module. Swapping the five patterns below is how the
IADI Core Principles or the Service Charter get parsed without touching
anything downstream.
"""

from __future__ import annotations

import re

from kifungu.ingest.parsers.base import Parser, RawNode

# Kenya Law's revised editions set Part headings in mixed case with an en-dash
# ("Part I - PRELIMINARY"); older gazette printings use uppercase. Accept both.
RE_PART = re.compile(r"^\s*PART\s+([IVXLC]+)\s*[\u2014\u2013-]\s*(.+?)\s*$", re.IGNORECASE)
# In the revised editions the section number stands alone on its line with the
# marginal side-note on the next, so the heading is optional here and recovered
# by _next_nonblank.
RE_SECTION = re.compile(r"^\s*(\d+)\.\s*(.*)$")
RE_BRACKETED = re.compile(r"^\s*\(([0-9a-zA-Z]+)\)\s*(.*)$")
# A table-of-contents entry: dot leaders running to a page number.
RE_TOC = re.compile(r"\.{4,}\s*\d+\s*$")

LEVEL = {"part": 0, "section": 1, "subsection": 2, "paragraph": 3, "subparagraph": 4}

_ROMAN = "ivxlcdm"


def _is_roman(token: str) -> bool:
    return bool(token) and all(ch in _ROMAN for ch in token.lower())


def _roman_to_int(token: str) -> int:
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    prev = 0
    for ch in reversed(token.lower()):
        value = values.get(ch, 0)
        total = total - value if value < prev else total + value
        prev = max(prev, value)
    return total


def _int_to_roman(n: int) -> str:
    table = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = []
    for value, sym in table:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def _letter_successor(last: str | None) -> str:
    if last is None:
        return "a"
    if len(last) == 1 and "a" <= last <= "y":
        return chr(ord(last) + 1)
    return ""


def _roman_successor(last: str | None) -> str:
    if last is None:
        return "i"
    return _int_to_roman(_roman_to_int(last) + 1)


def _next_nonblank(lines: list[str], start: int, limit: int = 3) -> str:
    """The marginal side-note that follows a bare section number."""
    for line in lines[start : start + limit]:
        candidate = line.strip()
        if candidate:
            # A heading, not the opening of the subsection body.
            return "" if candidate.startswith("(") else candidate
    return ""


class KenyaStatuteParser(Parser):
    name = "kenya_statute"

    def parse(self, text: str) -> list[RawNode]:
        markers = self._scan(text)
        return self._build(markers, len(text))

    # ---- pass 1: find structural markers ------------------------------------

    def _scan(self, text: str) -> list[tuple[str, str, int, str]]:
        """Return (kind, number, offset, heading) in document order."""
        found: list[tuple[str, str, int, str]] = []
        last_paragraph: str | None = None
        last_subparagraph: str | None = None
        in_paragraph = False

        lines = text.splitlines(keepends=True)
        offset = 0
        for index, line in enumerate(lines):
            stripped = line.rstrip("\n")

            # Contents pages repeat every section number in the document. Left
            # in, they would shadow the real body with phantom nodes whose text
            # is a row of dots.
            if RE_TOC.search(stripped):
                offset += len(line)
                continue

            part = RE_PART.match(stripped)
            if part:
                found.append(("part", part.group(1).upper(), offset, part.group(2).strip()))
                last_paragraph = last_subparagraph = None
                in_paragraph = False
                offset += len(line)
                continue

            section = RE_SECTION.match(stripped)
            if section:
                heading = section.group(2).strip()
                if not heading:
                    heading = _next_nonblank(lines, index + 1)
                found.append(("section", section.group(1), offset, heading[:120]))
                last_paragraph = last_subparagraph = None
                in_paragraph = False
                offset += len(line)
                continue

            bracketed = RE_BRACKETED.match(stripped)
            if bracketed:
                token = bracketed.group(1)
                if token.isdigit():
                    kind = "subsection"
                    last_paragraph = last_subparagraph = None
                    in_paragraph = False
                else:
                    kind = self._disambiguate(
                        token.lower(), last_paragraph, last_subparagraph, in_paragraph
                    )
                    if kind == "paragraph":
                        last_paragraph = token.lower()
                        last_subparagraph = None
                        in_paragraph = True
                    else:
                        last_subparagraph = token.lower()
                found.append((kind, token.lower(), offset, ""))

            offset += len(line)

        return found

    @staticmethod
    def _disambiguate(
        token: str,
        last_paragraph: str | None,
        last_subparagraph: str | None,
        in_paragraph: bool,
    ) -> str:
        """Decide whether '(i)' or '(v)' is a paragraph letter or a roman numeral.

        Only i, v and x are ambiguous. Sequence continuity settles almost every
        real case: '(i)' following '(h)' continues a lettered list, whereas
        '(i)' first-of-list inside a paragraph opens a roman one.
        """
        if token == _letter_successor(last_paragraph):
            return "paragraph"
        if in_paragraph and token == _roman_successor(last_subparagraph):
            return "subparagraph"
        if len(token) > 1 and _is_roman(token):
            return "subparagraph"
        if len(token) == 1 and token.isalpha() and token not in _ROMAN:
            return "paragraph"
        return "subparagraph" if in_paragraph else "paragraph"

    # ---- pass 2: nest them and assign spans ---------------------------------

    def _build(
        self, markers: list[tuple[str, str, int, str]], text_len: int
    ) -> list[RawNode]:
        nodes: list[RawNode] = []
        stack: list[RawNode] = []

        for i, (kind, number, offset, heading) in enumerate(markers):
            level = LEVEL[kind]

            # A node runs until the next marker at the same or a shallower level.
            end = text_len
            for kind2, _, offset2, _ in markers[i + 1 :]:
                if LEVEL[kind2] <= level:
                    end = offset2
                    break

            while stack and LEVEL[stack[-1].kind] >= level:
                stack.pop()
            parent = stack[-1] if stack else None

            node = RawNode(
                kind=kind,
                number=number,
                citation=self._citation(kind, number, parent),
                char_span=(offset, end),
                heading=heading,
                parent=parent.id if parent else None,
            )
            node.id = node.citation
            if parent is not None:
                parent.children.append(node.id)

            nodes.append(node)
            stack.append(node)

        return nodes

    @staticmethod
    def _citation(kind: str, number: str, parent: RawNode | None) -> str:
        if kind == "part":
            return f"Part {number}"
        if kind == "section":
            return f"s.{number}"
        base = parent.citation if parent is not None else "s.?"
        return f"{base}({number})"
