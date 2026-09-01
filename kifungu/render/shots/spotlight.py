"""`spotlight` — everything dims except the clause's own lines."""

from __future__ import annotations

from kifungu.render.easing import ramp
from kifungu.render.effects import dim_except, draw_image_fitted
from kifungu.render.shots.base import RenderContext, Shot, fitted_page_box


class Spotlight(Shot):
    name = "spotlight"
    z_order = 20
    requires = frozenset({"page_raster", "lines"})
    # The clause is lit precisely so it can be read, so the hold-time rule of
    # spec §4 applies to this shot.
    displays_reading_text = True

    def render(self, ctx: RenderContext, t_local: float) -> None:
        if ctx.node is None:
            raise ValueError("spotlight needs a source node; the Cut has no citation resolved")

        dim = float(self.param("dim", 0.22))
        feather = float(self.param("feather_px", 22.0))
        ramp_seconds = float(self.param("ramp", 0.45))
        pad = float(self.param("pad_px", 6.0))

        page = ctx.node.dominant_page
        image = ctx.page_image(page)
        # Same headroom as page_establish, so the page does not jump at the handoff.
        box = fitted_page_box(
            ctx, image, drift=float(self.param("drift", 0.03)),
            shadow=bool(self.param("shadow", True)),
        )
        draw_image_fitted(ctx.canvas, image, box)

        scale = box.width() / image.width()
        holes = [
            ctx.to_pixels(line.bbox, line.page, scale, box.left(), box.top()).makeOutset(pad, pad)
            for line in ctx.node.lines
            if line.page == page
        ]

        # Eased ramp in, and back out over the tail, so it is never a hard cut.
        rise = ramp(t_local, 0.0, ramp_seconds, "out_quint")
        fall = 1.0 - ramp(t_local, self.scene.dur - ramp_seconds, ramp_seconds, "in_out_cubic")
        amount = dim * min(rise, fall)

        # On an alpha profile the dim must stop at the edge of the page: dimming
        # the full frame would make every pixel opaque and the element unkeyable.
        if ctx.profile.alpha:
            ctx.canvas.save()
            ctx.canvas.clipRect(box)
            dim_except(ctx.canvas, ctx.profile.width, ctx.profile.height, holes,
                       ctx.brand.rgba("dim"), amount, feather)
            ctx.canvas.restore()
        else:
            dim_except(ctx.canvas, ctx.profile.width, ctx.profile.height, holes,
                       ctx.brand.rgba("dim"), amount, feather)
