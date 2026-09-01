"""`clause_zoom` — push in from the whole page onto the clause.

The third beat of the hunt: the scroll has landed on the page, the page is
established, and now the camera closes on the clause itself so that by the time
the selection is drawn the text is large enough to read.

The zoom is computed from the clause's own bounding box rather than given as a
number, so a two-line paragraph and a half-page subsection both end up filling
a comparable share of the frame.
"""

from __future__ import annotations

import skia

from kifungu.render.easing import get as ease
from kifungu.render.effects import draw_image_fitted
from kifungu.render.shots.base import RenderContext, Shot, focus_of, page_box

# Share of the *frame* the clause should occupy once the push-in settles.
# Measured against the frame rather than the safe area because a push-in is
# meant to crop the page — the safe area governs type, not the plate beneath it.
TARGET_FILL = 0.94
MAX_ZOOM = 6.0


class ClauseZoom(Shot):
    name = "clause_zoom"
    z_order = 12
    requires = frozenset({"page_raster", "lines"})

    def render(self, ctx: RenderContext, t_local: float) -> None:
        if ctx.node is None:
            raise ValueError("clause_zoom needs a source node; the Cut resolved no citation")

        page = ctx.node.dominant_page
        image = ctx.page_image(page)
        zoom = clause_zoom_factor(ctx, image, page, float(self.param("fill", TARGET_FILL)))
        focus = focus_of(ctx, ctx.node, page)

        held = bool(self.param("hold", False))
        if held:
            # Stay at the settled framing: lets a later shot sit on top of the
            # same view without recomputing the push.
            current_zoom, current_focus = zoom, focus
        else:
            p = ease(str(self.param("ease", "in_out_cubic")))(self.progress(t_local))
            current_zoom = 1.0 + (zoom - 1.0) * p
            current_focus = (
                0.5 + (focus[0] - 0.5) * p,
                0.5 + (focus[1] - 0.5) * p,
            )

        if not ctx.profile.alpha:
            ctx.canvas.drawRect(
                skia.Rect.MakeWH(ctx.profile.width, ctx.profile.height),
                skia.Paint(Color=_paper(ctx)),
            )

        box = page_box(ctx, image, zoom=current_zoom, focus=current_focus)
        draw_image_fitted(ctx.canvas, image, box)


def clause_zoom_factor(
    ctx: RenderContext, image: skia.Image, page: int, fill: float = TARGET_FILL
) -> float:
    """How far to push in so the clause fills `fill` of the frame.

    Both `clause_zoom` and `clause_select` call this, so the selection is drawn
    at exactly the framing the push-in settled on. If you override `fill`,
    override it on both scenes or the selection will land off the words.
    """
    node = ctx.node
    if node is None or ctx.corpus is None:
        return 1.0
    box = node.page_bbox(page)
    if box is None:
        return 1.0

    geometry = ctx.corpus.page_geometry(page)
    x0, y0, x1, y1 = box
    clause_w = max(1e-6, (x1 - x0) / geometry.width_pt)
    clause_h = max(1e-6, (y1 - y0) / geometry.height_pt)

    # The clause occupies clause_w x clause_h of the page; at zoom z it occupies
    # that share of a box z times larger. Fill the smaller dimension.
    base = page_box(ctx, image)
    fill_w = (ctx.profile.width * fill) / (base.width() * clause_w)
    fill_h = (ctx.profile.height * fill) / (base.height() * clause_h)
    return max(1.0, min(MAX_ZOOM, min(fill_w, fill_h)))


def _paper(ctx: RenderContext) -> int:
    from kifungu.render.text import color_of

    return color_of(ctx.brand.rgba("paper"))
