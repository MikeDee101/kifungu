"""A synthetic Kenyan-statute PDF, generated deterministically at test time.

CI cannot depend on the real Act: the file is large and its text carries its own
licensing. Generating a small statute in the same layout convention gives the
parser, geometry and verbatim tests something real to bite on while keeping the
repository free of third-party content.

The text below is invented. It is deliberately *not* a real statute.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

# (indent level, text). Indents mirror the gutter convention of a Kenyan Act.
BODY: list[tuple[int, str]] = [
    (0, "PART III - PROTECTION OF DEPOSITS"),
    (0, ""),
    (0, "12. Compensation to depositors"),
    (1, "(1) The Corporation shall pay to every depositor of an institution"),
    (1, "the following amounts-"),
    (2, "(a) the whole of the deposit, where it does not exceed the"),
    (2, "prescribed limit; or"),
    (2, "(b) an amount equal to the prescribed limit, comprising-"),
    (3, "(i) the principal sum held on deposit; and"),
    (3, "(ii) any interest accrued but unpaid."),
    (2, "(c) such further sums as the Board may prescribe."),
    (1, "(2) A payment under subsection (1) discharges the Corporation."),
    (0, ""),
    (0, "13. Subrogation"),
    (1, "(1) On making a payment under section 12, the Corporation is"),
    (1, "subrogated to the rights of the depositor."),
]

MARGIN_X = 64.0
MARGIN_Y = 90.0
LEADING = 18.0
INDENT = 22.0
FONT_SIZE = 10.5


def build(destination: Path) -> Path:
    """Write the fixture PDF. Byte-stable across runs for golden comparisons."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open()
    page = document.new_page(width=595, height=842)  # A4 in points

    y = MARGIN_Y
    for indent, line in BODY:
        if line:
            page.insert_text(
                (MARGIN_X + indent * INDENT, y),
                line,
                fontname="tiro",  # Times, metrically stable across platforms
                fontsize=FONT_SIZE,
            )
        y += LEADING

    document.save(destination, garbage=0, deflate=True)
    document.close()
    return destination
