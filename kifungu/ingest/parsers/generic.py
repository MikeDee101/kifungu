"""Fallback parser for documents with no statutory structure.

Splits on blank lines into numbered paragraphs. Used for the Service Charter,
press releases and anything reaching the engine through the synthetic-page
path, so those still get citations, spans and bboxes.
"""

from __future__ import annotations

import re

from kifungu.ingest.parsers.base import Parser, RawNode

RE_BLANK = re.compile(r"\n\s*\n")


class GenericParser(Parser):
    name = "generic"

    def parse(self, text: str) -> list[RawNode]:
        nodes: list[RawNode] = []
        index = 0
        cursor = 0
        for block in RE_BLANK.split(text):
            start = text.find(block, cursor)
            if start < 0 or not block.strip():
                cursor += len(block)
                continue
            index += 1
            end = start + len(block)
            nodes.append(
                RawNode(
                    kind="paragraph",
                    number=str(index),
                    citation=f"p.{index}",
                    char_span=(start, end),
                    id=f"p.{index}",
                )
            )
            cursor = end
        return nodes
