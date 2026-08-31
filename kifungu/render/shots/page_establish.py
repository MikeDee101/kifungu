"""`page_establish` — the page raster settles on a brand-tinted ground."""

from __future__ import annotations

import skia

from kifungu.render.easing import get as ease
from kifungu.render.effects import draw_image_fitted, drop_shadow_paint
from kifungu.render.shots.base import RenderContext, Shot, fitted_page_box


class PageEstablish(Shot):
    name = "page_establish"
    z_order = 10
    requires = frozenset({"page_raster"})

    def render(self, ctx: RenderContext, t_local: float) -> None:
        page = int(self.param("page", ctx.node.page if ctx.node else 1))
        drift = float(self.param("drift", 0.03))
        shadow = bool(self.param("shadow", True))

        # The broll profile must deliver a clean keyable element, so it gets no
        # background plate at all (spec §6).
        if not ctx.profile.alpha:
            ctx.canvas.drawRect(
                skia.Rect.MakeWH(ctx.profile.width, ctx.profile.height),
                skia.Paint(Color=_color(ctx, "paper")),
            )

        image = ctx.page_image(page)
        box = fitted_page_box(ctx, image, drift=drift, shadow=shadow)

        # A slow scale drift keeps the plate alive without reading as a zoom.
        p = ease("in_out_cubic")(self.progress(t_local))
        scale = 1.0 + drift * p
        box = _scaled(box, scale)

        if shadow:
            paint = drop_shadow_paint(0, box.height() * 0.010, box.height() * 0.014,
                                      ctx.brand.rgba("dim", 0.45))
            ctx.canvas.drawRect(box, paint)

        draw_image_fitted(ctx.canvas, image, box)


def _scaled(rect: skia.Rect, scale: float) -> skia.Rect:
    cx, cy = rect.centerX(), rect.centerY()
    w, h = rect.width() * scale, rect.height() * scale
    return skia.Rect.MakeXYWH(cx - w / 2, cy - h / 2, w, h)


def _color(ctx: RenderContext, token: str) -> int:
    from kifungu.render.text import color_of

    return color_of(ctx.brand.rgba(token))
