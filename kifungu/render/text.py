"""Typesetting (spec §5).

All text in the engine goes through here, and this is the only module that
knows how text is shaped. The spec's rule is that the engine must never use a
toy text API: real shaping, kerning, line breaking, justification and
diacritics or it will look amateur on justified legal text.

That is satisfied by Skia's Paragraph API (SkParagraph), which shapes with
HarfBuzz and breaks lines with ICU — the same path a browser takes. Shots call
into this module and never import skia text APIs themselves, so replacing the
shaper stays a change to one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import skia
from skia import textlayout as tl

from kifungu.brand import RGBA

ALIGN = {
    "left": tl.TextAlign.kLeft,
    "right": tl.TextAlign.kRight,
    "center": tl.TextAlign.kCenter,
    "justify": tl.TextAlign.kJustify,
    "start": tl.TextAlign.kStart,
    "end": tl.TextAlign.kEnd,
}


@lru_cache(maxsize=1)
def _unicode() -> skia.Unicode:
    # Skia looks for icudtl.dat beside the running executable and falls back to
    # a builtin when it is absent; release builds ship the file next to
    # kifungu.exe. Cached because building it per frame would be wasteful and
    # would repeat the loader's message on stderr.
    return skia.Unicode.ICU_Make()


@lru_cache(maxsize=1)
def _fonts() -> tl.FontCollection:
    collection = tl.FontCollection()
    collection.setDefaultFontManager(skia.FontMgr.RefDefault())
    return collection


def color_of(rgba: RGBA) -> int:
    r, g, b, a = rgba
    return skia.ColorSetARGB(
        int(round(a * 255)), int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
    )


@dataclass
class TextSpec:
    """A block of text and how it should be set."""

    text: str
    families: list[str]
    size: float
    color: RGBA
    align: str = "left"
    letter_spacing: float = 0.0
    word_spacing: float = 0.0
    weight: int = 400
    italic: bool = False
    emphasis: list[tuple[int, int]] = field(default_factory=list)
    emphasis_color: RGBA | None = None


def _text_style(spec: TextSpec, color: RGBA) -> tl.TextStyle:
    style = tl.TextStyle()
    style.setFontFamilies(list(spec.families))
    style.setFontSize(spec.size)
    style.setColor(color_of(color))
    style.setLetterSpacing(spec.letter_spacing)
    style.setWordSpacing(spec.word_spacing)
    style.setFontStyle(
        skia.FontStyle(
            spec.weight,
            skia.FontStyle.kNormal_Width,
            skia.FontStyle.kItalic_Slant if spec.italic else skia.FontStyle.kUpright_Slant,
        )
    )
    return style


def _emphasis_segments(spec: TextSpec) -> list[tuple[int, int, bool]]:
    """Split the string into (start, end, is_emphasised) runs."""
    if not spec.emphasis or spec.emphasis_color is None:
        return [(0, len(spec.text), False)]

    spans = sorted(spec.emphasis)
    segments: list[tuple[int, int, bool]] = []
    cursor = 0
    for start, end in spans:
        start = max(start, cursor)
        if end <= start:
            continue
        if start > cursor:
            segments.append((cursor, start, False))
        segments.append((start, end, True))
        cursor = end
    if cursor < len(spec.text):
        segments.append((cursor, len(spec.text), False))
    return segments


def layout(spec: TextSpec, width: float) -> tl.Paragraph:
    """Shape and break `spec` to `width` pixels."""
    paragraph_style = tl.ParagraphStyle()
    paragraph_style.setTextStyle(_text_style(spec, spec.color))
    paragraph_style.setTextAlign(ALIGN.get(spec.align, tl.TextAlign.kLeft))

    builder = tl.ParagraphBuilder.make(paragraph_style, _fonts(), _unicode())
    for start, end, emphasised in _emphasis_segments(spec):
        chunk = spec.text[start:end]
        if not chunk:
            continue
        if emphasised and spec.emphasis_color is not None:
            builder.pushStyle(_text_style(spec, spec.emphasis_color))
            builder.addText(chunk)
            builder.pop()
        else:
            builder.addText(chunk)

    paragraph = builder.Build()
    paragraph.layout(width)
    return paragraph


def draw(canvas: skia.Canvas, spec: TextSpec, x: float, y: float, width: float) -> float:
    """Draw text at (x, y) within `width`. Returns the height consumed."""
    paragraph = layout(spec, width)
    paragraph.paint(canvas, x, y)
    return float(paragraph.Height)


def measure(spec: TextSpec, width: float) -> tuple[float, float]:
    """(height, longest_line) without drawing — for fitting and safe-area checks."""
    paragraph = layout(spec, width)
    return float(paragraph.Height), float(paragraph.LongestLine)


def fit_size(spec: TextSpec, width: float, max_height: float, min_size: float = 12.0) -> float:
    """Largest font size at or below spec.size that fits inside max_height."""
    size = spec.size
    while size > min_size:
        trial = TextSpec(**{**spec.__dict__, "size": size})
        height, _ = measure(trial, width)
        if height <= max_height:
            return size
        size -= max(1.0, size * 0.06)
    return min_size
