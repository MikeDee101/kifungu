"""The corpus format (spec §3) — the contract between ingest and render.

One directory per document::

    corpus/<doc_id>/
      meta.json        provenance, page geometry, raster scale
      doc.json         the node tree (parts -> sections -> ... -> paragraphs)
      text.txt         canonical full text; every node's char_span indexes into this
      words.jsonl      one word per line, with its bbox in PDF points
      pages/p{n}@2x.png
      index.sqlite     FTS5 over normalised node text

Two rules here are load-bearing:

* **Geometry is stored in PDF points, never pixels** (spec §3.1). Rasters may be
  re-rendered at a different DPI; a corpus that baked pixel coordinates would
  silently misplace every highlight.
* **`text` is raw and `text_norm` is derived.** Extraction yields ligature
  codepoints (U+FB03 and friends), and verbatim lock (§8.1) asserts byte
  identity against the raw string, so `text` must never be normalised. Search
  needs the opposite, hence a second field that is indexed but never rendered.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

# A rectangle in PDF points: (x0, y0, x1, y1), origin top-left.
BBox = tuple[float, float, float, float]


def normalise(text: str) -> str:
    """Fold text for indexing and matching. Never use the result for rendering."""
    return unicodedata.normalize("NFKC", text).casefold()


def union(boxes: list[BBox]) -> BBox | None:
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


class Word(BaseModel):
    page: int
    index: int
    bbox: BBox
    text: str


class Line(BaseModel):
    """One visual line of a node, as a single rect in PDF points.

    Per-line rects are what make a highlighter sweep read as a highlighter
    rather than one fat rectangle (spec §3.1).
    """

    page: int
    bbox: BBox
    text: str


class Node(BaseModel):
    id: str
    kind: str  # part | section | subsection | paragraph | subparagraph
    citation: str  # canonical, e.g. "s.27(1)(a)"
    number: str = ""
    heading: str = ""
    page: int
    char_span: tuple[int, int]
    text: str  # raw, authoritative — verbatim lock tests against this
    text_norm: str = ""
    lines: list[Line] = Field(default_factory=list)
    bbox_union: BBox | None = None
    children: list[str] = Field(default_factory=list)
    parent: str | None = None

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def dominant_page(self) -> int:
        """The page holding most of this node.

        A clause that runs over a page break starts on one page and finishes on
        the next. Framing it on whichever page carries the bulk of it shows more
        of the clause than defaulting to wherever its first word happened to
        fall.
        """
        if not self.lines:
            return self.page
        counts: dict[int, int] = {}
        for line in self.lines:
            counts[line.page] = counts.get(line.page, 0) + 1
        return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]

    def page_bbox(self, page: int) -> BBox | None:
        """Union of this node's lines *on one page*.

        `bbox_union` spans every page the node touches, which for a clause
        crossing a page break describes a rectangle that exists on neither.
        Anything positioning a camera or a selection must use this instead.
        """
        return union([line.bbox for line in self.lines if line.page == page])


class PageGeometry(BaseModel):
    number: int
    width_pt: float
    height_pt: float
    raster_width_px: int
    raster_height_px: int

    @property
    def scale(self) -> float:
        """Pixels per PDF point for this page's raster."""
        return self.raster_width_px / self.width_pt


class Meta(BaseModel):
    doc_id: str
    title: str
    short_title: str = ""
    sha256: str
    source_filename: str
    ingested: str
    engine_version: str
    parser: str
    page_count: int
    raster_dpi: int
    pages: list[PageGeometry] = Field(default_factory=list)


class Corpus(BaseModel):
    """An ingested document, loaded from disk."""

    meta: Meta
    nodes: dict[str, Node] = Field(default_factory=dict)
    roots: list[str] = Field(default_factory=list)
    full_text: str = ""
    root_dir: Path | None = None

    model_config = {"arbitrary_types_allowed": True}

    # ---- lookup -------------------------------------------------------------

    def by_citation(self, citation: str) -> Node:
        wanted = citation.strip().casefold()
        for node in self.nodes.values():
            if node.citation.casefold() == wanted:
                return node
        raise KeyError(
            f"no node with citation {citation!r} in {self.meta.doc_id!r}. "
            f"Try `kifungu find` to locate it."
        )

    def page_geometry(self, page: int) -> PageGeometry:
        for geom in self.meta.pages:
            if geom.number == page:
                return geom
        raise KeyError(f"page {page} not in corpus {self.meta.doc_id!r}")

    def page_raster(self, page: int) -> Path:
        if self.root_dir is None:
            raise ValueError("corpus was not loaded from disk; no raster path available")
        path = self.root_dir / "pages" / f"p{page}@2x.png"
        if not path.is_file():
            raise FileNotFoundError(f"missing page raster {path}")
        return path

    def verify_verbatim(self, node: Node) -> bool:
        """Spec §8.1 — the node's text is exactly the source substring."""
        start, end = node.char_span
        return self.full_text[start:end] == node.text

    # ---- persistence --------------------------------------------------------

    def write(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "meta.json").write_text(
            self.meta.model_dump_json(indent=2), encoding="utf-8"
        )
        (root / "text.txt").write_text(self.full_text, encoding="utf-8")
        tree = {
            "roots": self.roots,
            "nodes": {k: json.loads(v.model_dump_json()) for k, v in self.nodes.items()},
        }
        (root / "doc.json").write_text(
            json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, root: Path) -> Corpus:
        root = Path(root)
        if not (root / "meta.json").is_file():
            raise FileNotFoundError(
                f"no corpus at {root}. Run `kifungu ingest` for this document first."
            )
        meta = Meta.model_validate_json((root / "meta.json").read_text(encoding="utf-8"))
        tree = json.loads((root / "doc.json").read_text(encoding="utf-8"))
        return cls(
            meta=meta,
            nodes={k: Node.model_validate(v) for k, v in tree["nodes"].items()},
            roots=tree.get("roots", []),
            full_text=(root / "text.txt").read_text(encoding="utf-8"),
            root_dir=root,
        )


def corpus_dir(doc_id: str, base: Path | None = None) -> Path:
    return (base or Path.cwd() / "corpus") / doc_id
