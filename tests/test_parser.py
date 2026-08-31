"""Structure detection (spec §3.1) and the bbox goldens of §13."""

from __future__ import annotations

from kifungu.corpus import Corpus
from kifungu.ingest.parsers import get_parser

SAMPLE = """PART V - PROTECTION OF DEPOSITS

27. Compensation to depositors
(1) The Corporation shall pay the following-
(a) the whole amount; or
(b) a limited amount, comprising-
(i) principal sums; and
(ii) accrued interest.
(c) such other sums as may be prescribed.

28. Subrogation
(1) The Corporation is subrogated.
"""


def test_citations_are_canonical():
    nodes = {n.citation for n in get_parser("kenya_statute").parse(SAMPLE)}
    assert {"Part V", "s.27", "s.27(1)", "s.27(1)(a)", "s.28", "s.28(1)"} <= nodes


def test_roman_subparagraphs_nest_under_their_paragraph():
    """'(i)' opening a list inside (b) is a sub-paragraph, not paragraph (i)."""
    nodes = {n.citation: n for n in get_parser("kenya_statute").parse(SAMPLE)}
    assert "s.27(1)(b)(i)" in nodes
    assert "s.27(1)(b)(ii)" in nodes
    assert nodes["s.27(1)(b)(i)"].kind == "subparagraph"


def test_lettered_list_resumes_after_a_roman_sublist():
    """(c) must follow (b) as a paragraph, not be swallowed by the roman list."""
    nodes = {n.citation: n for n in get_parser("kenya_statute").parse(SAMPLE)}
    assert nodes["s.27(1)(c)"].kind == "paragraph"


def test_i_after_h_continues_the_lettered_list():
    text = "1. Heading\n(1) Body-\n" + "".join(
        f"({chr(ord('a') + i)}) item {i};\n" for i in range(9)
    )
    nodes = {n.citation: n for n in get_parser("kenya_statute").parse(text)}
    assert nodes["s.1(1)(i)"].kind == "paragraph"


def test_spans_are_nested_within_the_parent():
    nodes = {n.citation: n for n in get_parser("kenya_statute").parse(SAMPLE)}
    parent = nodes["s.27(1)"]
    child = nodes["s.27(1)(a)"]
    assert parent.char_span[0] <= child.char_span[0]
    assert child.char_span[1] <= parent.char_span[1]


def test_generic_parser_numbers_paragraphs():
    nodes = get_parser("generic").parse("First block.\n\nSecond block.\n\nThird block.")
    assert [n.citation for n in nodes] == ["p.1", "p.2", "p.3"]


# ---- geometry -------------------------------------------------------------


def test_nodes_carry_per_line_boxes(corpus: Corpus):
    """Per-line rects, not one union — this is what makes a sweep look manual."""
    node = corpus.by_citation("s.12(1)")
    assert len(node.lines) >= 2
    for line in node.lines:
        x0, y0, x1, y1 = line.bbox
        assert x1 > x0 and y1 > y0


def test_geometry_is_in_pdf_points_not_pixels(corpus: Corpus):
    """A box must never exceed the page's point dimensions (spec §3.1)."""
    node = corpus.by_citation("s.12(1)")
    geometry = corpus.page_geometry(node.page)
    for line in node.lines:
        assert 0 <= line.bbox[0] < geometry.width_pt
        assert 0 <= line.bbox[3] <= geometry.height_pt
    # The raster is larger than the page in points, so pixels would overflow.
    assert geometry.raster_width_px > geometry.width_pt


def test_bbox_golden_ordering(corpus: Corpus):
    """Sub-paragraphs sit below their paragraph on the page."""
    b = corpus.by_citation("s.12(1)(b)")
    i = corpus.by_citation("s.12(1)(b)(i)")
    assert b.bbox_union is not None and i.bbox_union is not None
    assert i.bbox_union[1] >= b.bbox_union[1]
