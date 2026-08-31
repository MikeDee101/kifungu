"""Structure parsers. One module per document convention (spec §3.1)."""

from __future__ import annotations

from kifungu.ingest.parsers.base import Marker, Parser, RawNode
from kifungu.ingest.parsers.generic import GenericParser
from kifungu.ingest.parsers.kenya_statute import KenyaStatuteParser

PARSERS: dict[str, type[Parser]] = {
    "kenya_statute": KenyaStatuteParser,
    "generic": GenericParser,
}


def get_parser(name: str) -> Parser:
    try:
        return PARSERS[name]()
    except KeyError:
        raise KeyError(f"unknown parser {name!r}; available: {sorted(PARSERS)}") from None


__all__ = [
    "PARSERS",
    "GenericParser",
    "KenyaStatuteParser",
    "Marker",
    "Parser",
    "RawNode",
    "get_parser",
]
