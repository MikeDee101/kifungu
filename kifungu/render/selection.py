"""Selection styles — how the engine points at a clause.

The spec names two of these as shots (`marker_sweep`, `underline_draw`), but in
practice the *gesture* is the variable an operator wants to choose while the
rest of the clip stays put. So the gesture lives here as a registry of styles,
and the shot that draws one simply takes a `style` parameter.

Adding a style is a class and one registry line — the same growth story as the
shot library, one level down.

Every style receives the clause's per-line rectangles in frame pixels, already
converted from PDF points by the shot. All jitter is drawn from a seeded RNG so
that re-rendering a Cut after a copy edit still matches frame for frame (§6).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import ClassVar

import skia

from kifungu.brand import Brand
from kifungu.render.easing import clamp01
from kifungu.render.easing import get as ease
from kifungu.render.text import color_of


@dataclass
class SelectionContext:
    """What a style needs to draw itself."""

    canvas: skia.Canvas
    lines: list[skia.Rect]
    union: skia.Rect
    brand: Brand
    rng: random.Random
    progress: float  # 0..1 across the shot
    elapsed: float  # seconds since the shot began, for continuous motion
    params: dict


class SelectionStyle:
    name: ClassVar[str] = "style"
    description: ClassVar[str] = ""

    def draw(self, sc: SelectionContext) -> None:
        raise NotImplementedError

    # -- shared helpers ----------------------------------------------------

    @staticmethod
    def accent(sc: SelectionContext, alpha: float = 1.0) -> int:
        token = str(sc.params.get("color", "accent"))
        return color_of(sc.brand.rgba(token, alpha))

    @staticmethod
    def staggered(sc: SelectionContext, index: int, count: int, stagger: float) -> float:
        """Progress of one line when lines start in sequence."""
        if count <= 1 or stagger <= 0:
            return sc.progress
        span = 1.0 / (1.0 + stagger * (count - 1))
        start = index * stagger * span
        return clamp01((sc.progress - start) / span)

    @staticmethod
    def trimmed(path: skia.Path, fraction: float) -> skia.Path:
        """The first `fraction` of a path, for draw-on animation."""
        out = skia.Path()
        measure = skia.PathMeasure(path, False)
        while True:
            length = measure.getLength()
            if length > 0:
                measure.getSegment(0.0, length * clamp01(fraction), out, True)
            if not measure.nextContour():
                break
        return out


class MarkerSweep(SelectionStyle):
    name = "marker_sweep"
    description = "Highlighter wipe across each line, staggered, with a hand's wobble."

    def draw(self, sc: SelectionContext) -> None:
        alpha = float(sc.params.get("alpha", 0.35))
        stagger = float(sc.params.get("stagger", 0.09))
        wobble = float(sc.params.get("wobble_px", 1.5))
        pad = float(sc.params.get("pad_px", 3.0))

        paint = skia.Paint(AntiAlias=True, Color=self.accent(sc, alpha))
        for index, rect in enumerate(sc.lines):
            p = ease("out_quint")(self.staggered(sc, index, len(sc.lines), stagger))
            if p <= 0.0:
                continue
            width = rect.width() * p
            # A marker is held at a slight angle and does not end square, so the
            # top and bottom edges wander by a pixel or two.
            top = rect.top() - pad + sc.rng.uniform(-wobble, wobble)
            bottom = rect.bottom() + pad + sc.rng.uniform(-wobble, wobble)
            path = skia.Path()
            path.moveTo(rect.left() - pad, top)
            path.lineTo(rect.left() - pad + width, top + sc.rng.uniform(-wobble, wobble))
            path.lineTo(rect.left() - pad + width, bottom + sc.rng.uniform(-wobble, wobble))
            path.lineTo(rect.left() - pad, bottom)
            path.close()
            sc.canvas.drawPath(path, paint)


class Underline(SelectionStyle):
    name = "underline"
    description = "A stroke drawn under each line. Lighter than a highlighter."

    def draw(self, sc: SelectionContext) -> None:
        stagger = float(sc.params.get("stagger", 0.10))
        thickness = float(sc.params.get("thickness_px", 0.0))
        paint = skia.Paint(
            AntiAlias=True,
            Color=self.accent(sc, float(sc.params.get("alpha", 0.95))),
            Style=skia.Paint.kStroke_Style,
            StrokeCap=skia.Paint.kRound_Cap,
        )
        for index, rect in enumerate(sc.lines):
            p = ease("out_quint")(self.staggered(sc, index, len(sc.lines), stagger))
            if p <= 0.0:
                continue
            paint.setStrokeWidth(thickness or max(2.0, rect.height() * 0.10))
            y = rect.bottom() + rect.height() * 0.12
            sc.canvas.drawLine(rect.left(), y, rect.left() + rect.width() * p, y, paint)


class HandCircle(SelectionStyle):
    name = "hand_circle"
    description = "A looping hand-drawn circle around the clause, as if ringed in pen."

    def draw(self, sc: SelectionContext) -> None:
        turns = float(sc.params.get("turns", 1.15))
        wobble = float(sc.params.get("wobble", 0.028))
        overshoot = float(sc.params.get("pad", 0.10))
        thickness = float(sc.params.get("thickness_px", 0.0))

        box = sc.union
        rx = box.width() * (0.5 + overshoot)
        ry = box.height() * (0.5 + overshoot * 2.2)
        cx, cy = box.centerX(), box.centerY()

        # A drawn-by-hand ring: the radius breathes with a couple of low
        # harmonics, and the whole loop is tilted slightly off-axis.
        phase = sc.rng.uniform(0.0, math.tau)
        tilt = sc.rng.uniform(-0.06, 0.06)
        a1, a2 = sc.rng.uniform(0.5, 1.0), sc.rng.uniform(0.3, 0.8)

        steps = 160
        sweep = math.tau * turns * ease("out_cubic")(sc.progress)
        path = skia.Path()
        for i in range(steps + 1):
            angle = -math.pi / 2.0 + sweep * (i / steps)
            wob = 1.0 + wobble * (a1 * math.sin(angle * 3.0 + phase)
                                  + a2 * math.sin(angle * 5.0 + phase * 1.7))
            x = cx + math.cos(angle + tilt) * rx * wob
            y = cy + math.sin(angle + tilt) * ry * wob
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)

        paint = skia.Paint(
            AntiAlias=True,
            Color=self.accent(sc, float(sc.params.get("alpha", 0.95))),
            Style=skia.Paint.kStroke_Style,
            StrokeCap=skia.Paint.kRound_Cap,
            StrokeWidth=thickness or max(3.0, box.height() * 0.045),
        )
        # Softens the polyline into something closer to an ink stroke.
        paint.setPathEffect(skia.CornerPathEffect.Make(8.0))
        sc.canvas.drawPath(path, paint)


class BoundingBox(SelectionStyle):
    name = "bounding_box"
    description = "A clean rectangle drawn on from one corner."

    def draw(self, sc: SelectionContext) -> None:
        pad = float(sc.params.get("pad_px", 10.0))
        radius = float(sc.params.get("radius_px", 4.0))
        fill = float(sc.params.get("fill_alpha", 0.10))

        box = sc.union.makeOutset(pad, pad)
        if fill > 0:
            sc.canvas.drawRRect(
                skia.RRect.MakeRectXY(box, radius, radius),
                skia.Paint(AntiAlias=True,
                           Color=self.accent(sc, fill * ease("out_quint")(sc.progress))),
            )

        outline = skia.Path()
        outline.addRRect(skia.RRect.MakeRectXY(box, radius, radius))
        paint = skia.Paint(
            AntiAlias=True,
            Color=self.accent(sc, float(sc.params.get("alpha", 1.0))),
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=float(sc.params.get("thickness_px", 3.0)),
        )
        sc.canvas.drawPath(self.trimmed(outline, ease("out_quint")(sc.progress)), paint)


class Marquee(SelectionStyle):
    name = "marquee"
    description = "A marching-ants selection box, in the manner of an image editor."

    def draw(self, sc: SelectionContext) -> None:
        pad = float(sc.params.get("pad_px", 8.0))
        dash = float(sc.params.get("dash_px", 9.0))
        speed = float(sc.params.get("speed", 26.0))
        fill = float(sc.params.get("fill_alpha", 0.08))

        box = sc.union.makeOutset(pad, pad)
        grow = ease("out_quint")(clamp01(sc.progress / 0.25))
        box = skia.Rect.MakeXYWH(
            box.centerX() - box.width() * grow / 2.0,
            box.centerY() - box.height() * grow / 2.0,
            box.width() * grow,
            box.height() * grow,
        )
        if grow <= 0.0:
            return

        if fill > 0:
            sc.canvas.drawRect(box, skia.Paint(AntiAlias=True, Color=self.accent(sc, fill)))

        # Two offset dashed strokes, light over dark, so the ants read against
        # both the paper and the ink beneath them.
        under = skia.Paint(
            AntiAlias=True, Style=skia.Paint.kStroke_Style,
            StrokeWidth=float(sc.params.get("thickness_px", 2.0)),
            Color=color_of(sc.brand.rgba("ink", 0.85)),
        )
        over = skia.Paint(
            AntiAlias=True, Style=skia.Paint.kStroke_Style,
            StrokeWidth=float(sc.params.get("thickness_px", 2.0)),
            Color=color_of(sc.brand.rgba("paper", 0.95)),
        )
        # The ants march continuously with elapsed time, not with progress:
        # they must keep moving while the shot holds.
        phase = -sc.elapsed * speed
        under.setPathEffect(skia.DashPathEffect.Make([dash, dash], phase))
        over.setPathEffect(skia.DashPathEffect.Make([dash, dash], phase + dash))
        sc.canvas.drawRect(box, under)
        sc.canvas.drawRect(box, over)


class CornerBrackets(SelectionStyle):
    name = "brackets"
    description = "Four corner brackets that snap in, like a crop or focus reticle."

    def draw(self, sc: SelectionContext) -> None:
        pad = float(sc.params.get("pad_px", 14.0))
        arm = float(sc.params.get("arm", 0.18))
        box = sc.union.makeOutset(pad, pad)

        p = ease("out_back")(sc.progress)
        spread = 1.0 + (1.0 - p) * 0.16
        box = skia.Rect.MakeXYWH(
            box.centerX() - box.width() * spread / 2.0,
            box.centerY() - box.height() * spread / 2.0,
            box.width() * spread,
            box.height() * spread,
        )

        ax = box.width() * arm
        ay = box.height() * arm
        paint = skia.Paint(
            AntiAlias=True,
            Color=self.accent(sc, clamp01(sc.progress * 3.0)),
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=float(sc.params.get("thickness_px", 4.0)),
            StrokeCap=skia.Paint.kSquare_Cap,
        )
        corners = [
            (box.left(), box.top(), 1, 1),
            (box.right(), box.top(), -1, 1),
            (box.left(), box.bottom(), 1, -1),
            (box.right(), box.bottom(), -1, -1),
        ]
        for x, y, sx, sy in corners:
            path = skia.Path()
            path.moveTo(x + sx * ax, y)
            path.lineTo(x, y)
            path.lineTo(x, y + sy * ay)
            sc.canvas.drawPath(path, paint)


STYLES: dict[str, type[SelectionStyle]] = {
    style.name: style
    for style in (MarkerSweep, Underline, HandCircle, BoundingBox, Marquee, CornerBrackets)
}


def get(name: str) -> SelectionStyle:
    try:
        return STYLES[name]()
    except KeyError:
        raise KeyError(
            f"unknown selection style {name!r}; available: {sorted(STYLES)}"
        ) from None
