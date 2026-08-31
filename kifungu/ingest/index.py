"""Full-text search over a corpus (spec §3.3).

SQLite FTS5 over normalised node text, so the operator can go from "the bit
about the KES 500,000 cap" to `s.27(1)` without opening the PDF.

The index is built over `text_norm` and never over `text`: ligatures and
casing must not affect matching, but must survive into what gets rendered.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from kifungu.corpus import Corpus, normalise

INDEX_NAME = "index.sqlite"


@dataclass
class Hit:
    citation: str
    kind: str
    page: int
    score: float
    snippet: str


def build_index(corpus: Corpus, root: Path) -> Path:
    path = Path(root) / INDEX_NAME
    path.unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE nodes USING fts5("
            "  citation UNINDEXED, kind UNINDEXED, page UNINDEXED,"
            "  body, tokenize='unicode61 remove_diacritics 2')"
        )
        connection.executemany(
            "INSERT INTO nodes (citation, kind, page, body) VALUES (?, ?, ?, ?)",
            [
                (n.citation, n.kind, n.page, n.text_norm or normalise(n.text))
                for n in corpus.nodes.values()
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return path


def _to_match_query(query: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression.

    Every token is quoted, so operator input containing '-', '(' or a bare
    'AND' cannot become a syntax error in front of a non-technical user.
    """
    tokens = [t for t in normalise(query).replace('"', " ").split() if t]
    if not tokens:
        raise ValueError("empty search query")
    return " ".join(f'"{t}"' for t in tokens)


def search(root: Path, query: str, limit: int = 10, kinds: list[str] | None = None) -> list[Hit]:
    path = Path(root) / INDEX_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"no search index at {path}. Re-run `kifungu ingest` for this document."
        )

    sql = (
        "SELECT citation, kind, page, bm25(nodes) AS score,"
        "       snippet(nodes, 3, '', '', '\u2026', 14) AS snip "
        "FROM nodes WHERE nodes MATCH ?"
    )
    params: list[object] = [_to_match_query(query)]
    if kinds:
        sql += " AND kind IN (" + ",".join("?" * len(kinds)) + ")"
        params.extend(kinds)
    sql += " ORDER BY score LIMIT ?"
    params.append(limit)

    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()

    return [Hit(citation=r[0], kind=r[1], page=r[2], score=r[3], snippet=r[4]) for r in rows]
