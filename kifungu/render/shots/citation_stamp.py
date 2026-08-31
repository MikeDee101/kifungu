"""`citation_stamp` — citation, short title and year stamp in with an overshoot.

Mandatory on every public profile (spec §8.4): the engine quotes an Act of
Parliament under the Corporation's name, and an unattributed quote is the one
output this engine must never produce.
"""

from __future__ import annotations

import skia

from kifungu.render.easing import ramp
from kifungu.render.shots.base import RenderContext, Shot
from kifungu.render.text import TextSpec, draw, measure


class CitationStamp(Shot):
    name = "citation_stamp"
    z_order = 80
    requires = frozenset()

    def render(self, ctx: RenderContext, t_local: float) -> None:
        citation = str(self.param("citation", ctx.cut.source.citation))
        title = str(self.param("title", ctx.cut.source.title))
        if not citation:
            raise ValueError("citation_stamp has no citation to stamp")

        grid = ctx.grid
        size = float(self.param("size", grid.width * 0.032))
        pad = size * 0.7

        # Overshoot on entry, then hold.
        p = ramp(t_local, 0.0, float(self.param("rise", 0.45)), "out_back")
        alpha = ramp(t_local, 0.0, 0.25, "out_quint")
        offset = (1.0 - p) * size * 1.4

        label = TextSpec(
            text=citation,
            families=ctx.brand.families("mono"),
            size=size,
            color=ctx.brand.rgba("paper", alpha),
            weight=700,
        )
        sub = TextSpec(
            text=title,
            families=ctx.brand.families("body"),
            size=size * 0.62,
            color=ctx.brand.rgba("paper", alpha * 0.85),
        )

        width = grid.content_width
        label_h, label_w = measure(label, width)
        sub_h, sub_w = measure(sub, width)

        block_w = max(label_w, sub_w) + pad * 2
        block_h = label_h + sub_h + pad * 1.6
        x = grid.left
        y = grid.bottom - block_h + offset

        plate = skia.Paint(AntiAlias=True)
        plate.setColor(_argb(ctx.brand.rgba("primary", 0.92 * alpha)))
        ctx.canvas.drawRRect(
            skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, block_w, block_h), size * 0.18,
                                  size * 0.18),
            plate,
        )

        draw(ctx.canvas, label, x + pad, y + pad * 0.7, width)
        draw(ctx.canvas, sub, x + pad, y + pad * 0.7 + label_h, width)


def _argb(rgba) -> int:
    from kifungu.render.text import color_of

    return color_of(rgba)
