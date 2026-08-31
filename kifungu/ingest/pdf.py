"""Authentic-page ingest (spec §3.1).

Used when the look of the real document is part of the message. Produces the
corpus format: page rasters, word geometry, a node tree and pinned provenance.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pymupdf

from kifungu import __version__
from kifungu.corpus import Corpus, Line, Meta, Node, PageGeometry, Word, normalise, union
from kifungu.ingest.parsers import get_parser

# Below this many extracted words per page on average, the PDF is a scan.
MIN_WORDS_PER_PAGE = 5


class ScannedDocumentError(RuntimeError):
    """Raised when a PDF carries no usable text layer."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _TextBuilder:
    """Rebuilds document text from words, keeping an exact offset for each.

    The canonical text is a reconstruction rather than `page.get_text()`, so
    that every character offset maps to a known word box. Verbatim lock (§8.1)
    asserts against this same string, which makes the guarantee internally
    exact rather than approximately aligned.
    """

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.length = 0
        self.words: list[Word] = []
        self.spans: list[tuple[int, int]] = []
        self.line_of_word: list[tuple[int, int, int]] = []

    def _append(self, text: str) -> None:
        self.parts.append(text)
        self.length += len(text)

    def add_page(self, page_number: int, raw_words: list[tuple]) -> None:
        if self.parts:
            self._append("\n\n")
        previous: tuple[int, int] | None = None
        for index, entry in enumerate(raw_words):
            x0, y0, x1, y1, text, block, line, _word_no = entry[:8]
            key = (int(block), int(line))
            if previous is not None:
                if key[0] != previous[0]:
                    self._append("\n\n")
                elif key[1] != previous[1]:
                    self._append("\n")
                else:
                    self._append(" ")
            start = self.length
            self._append(text)
            self.words.append(
                Word(
                    page=page_number,
                    index=index,
                    bbox=(float(x0), float(y0), float(x1), float(y1)),
                    text=text,
                )
            )
            self.spans.append((start, self.length))
            self.line_of_word.append((page_number, int(block), int(line)))
            previous = key

    @property
    def text(self) -> str:
        return "".join(self.parts)


def _lines_for_span(
    builder: _TextBuilder, span: tuple[int, int]
) -> tuple[list[Line], int | None]:
    """Group the words covered by a char span into per-line rects.

    Per-line rects — not one union — are what let a highlighter sweep stagger
    across lines and read as a hand rather than a rectangle (spec §5).
    """
    start, end = span
    grouped: dict[tuple[int, int, int], list[int]] = {}
    order: list[tuple[int, int, int]] = []
    for i, (ws, we) in enumerate(builder.spans):
        if we <= start or ws >= end:
            continue
        key = builder.line_of_word[i]
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(i)

    lines: list[Line] = []
    for key in order:
        indices = grouped[key]
        boxes = [builder.words[i].bbox for i in indices]
        rect = union(boxes)
        if rect is None:
            continue
        lines.append(
            Line(
                page=key[0],
                bbox=rect,
                text=" ".join(builder.words[i].text for i in indices),
            )
        )
    first_page = lines[0].page if lines else None
    return lines, first_page


def ingest_pdf(
    pdf_path: Path,
    doc_id: str,
    out_dir: Path,
    parser_name: str = "kenya_statute",
    dpi: int = 300,
    title: str | None = None,
    short_title: str = "",
) -> Corpus:
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"source PDF not found: {pdf_path}")

    document = pymupdf.open(pdf_path)
    out_dir = Path(out_dir)
    (out_dir / "pages").mkdir(parents=True, exist_ok=True)

    builder = _TextBuilder()
    geometries: list[PageGeometry] = []

    for page_index in range(document.page_count):
        page = document[page_index]
        number = page_index + 1
        raw_words = page.get_text("words")
        builder.add_page(number, raw_words)

        pixmap = page.get_pixmap(dpi=dpi)
        pixmap.save(out_dir / "pages" / f"p{number}@2x.png")
        geometries.append(
            PageGeometry(
                number=number,
                width_pt=float(page.rect.width),
                height_pt=float(page.rect.height),
                raster_width_px=pixmap.width,
                raster_height_px=pixmap.height,
            )
        )

    page_count = document.page_count
    document.close()

    # Verbatim lock is vacuous on a document with no text layer, so refuse it
    # loudly rather than writing a corpus that cannot be checked.
    if len(builder.words) < MIN_WORDS_PER_PAGE * page_count:
        raise ScannedDocumentError(
            f"{pdf_path.name} has almost no extractable text "
            f"({len(builder.words)} words across {page_count} page(s)) — it looks like a scan.\n"
            "  Kifungu cannot guarantee verbatim accuracy without a text layer.\n"
            "  OCR it first (e.g. `ocrmypdf in.pdf out.pdf`) and ingest the result."
        )

    full_text = builder.text
    raw_nodes = get_parser(parser_name).parse(full_text)

    nodes: dict[str, Node] = {}
    roots: list[str] = []
    for raw in raw_nodes:
        lines, first_page = _lines_for_span(builder, raw.char_span)
        text = full_text[raw.char_span[0] : raw.char_span[1]]
        nodes[raw.id] = Node(
            id=raw.id,
            kind=raw.kind,
            citation=raw.citation,
            number=raw.number,
            heading=raw.heading,
            page=first_page or 1,
            char_span=raw.char_span,
            text=text,
            text_norm=normalise(text),
            lines=lines,
            bbox_union=union([line.bbox for line in lines]),
            children=raw.children,
            parent=raw.parent,
        )
        if raw.parent is None:
            roots.append(raw.id)

    meta = Meta(
        doc_id=doc_id,
        title=title or pdf_path.stem,
        short_title=short_title,
        sha256=sha256_file(pdf_path),
        source_filename=pdf_path.name,
        ingested=datetime.now(UTC).isoformat(),
        engine_version=__version__,
        parser=parser_name,
        page_count=page_count,
        raster_dpi=dpi,
        pages=geometries,
    )

    corpus = Corpus(meta=meta, nodes=nodes, roots=roots, full_text=full_text, root_dir=out_dir)
    corpus.write(out_dir)

    with (out_dir / "words.jsonl").open("w", encoding="utf-8") as handle:
        for word in builder.words:
            handle.write(json.dumps(word.model_dump(), ensure_ascii=False) + "\n")

    return corpus
