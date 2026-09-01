"""`clause_select` — point at the clause in whichever style the operator picked.

The shot handles everything common to pointing at a clause: finding the lines,
converting their geometry from PDF points into frame pixels under the current
zoom, and seeding deterministic jitter. *How* the pointing looks is delegated to
a selection style (`kifungu.render.selection`), so choosing between a
highlighter, a hand-drawn ring and a marching-ants marquee is a parameter rather
than a different shot.

`marker_sweep` and `underline_draw` are registered separately because the spec
names them, but they are this shot with a style already chosen.
"""

from __future__ import annotations

import skia

from kifungu.render import selection
from kifungu.render.effects import draw_image_fitted
from kifungu.render.shots.base import RenderContext, Shot, focus_of, page_box
from kifungu.render.shots.clause_zoom import TARGET_FILL, clause_zoom_factor


class ClauseSelect(Shot):
    name = "clause_select"
    z_order = 30
    requires = frozenset({"page_raster", "lines"})
    # The clause is being pointed at so it can be read.
    displays_reading_text = True
    default_style = "marker_sweep"

    def render(self, ctx: RenderContext, t_local: float) -> None:
        if ctx.node is None:
            raise ValueError("clause_select needs a source node; the Cut resolved no citation")

        style_name = str(self.param("style", self.default_style))
        style = selection.get(style_name)

        page = ctx.node.dominant_page
        image = ctx.page_image(page)

        # Match whatever framing clause_zoom settled on, so the selection lands
        # exactly on the words rather than near them.
        zoom = 1.0
        focus = (0.5, 0.5)
        if bool(self.param("zoomed", True)):
            zoom = clause_zoom_factor(ctx, image, page, float(self.param("fill", TARGET_FILL)))
            focus = focus_of(ctx, ctx.node, page)

        if bool(self.param("draw_page", True)):
            if not ctx.profile.alpha:
                ctx.canvas.drawRect(
                    skia.Rect.MakeWH(ctx.profile.width, ctx.profile.height),
                    skia.Paint(Color=_paper(ctx)),
                )
            box = page_box(ctx, image, zoom=zoom, focus=focus)
            draw_image_fitted(ctx.canvas, image, box)
        else:
            box = page_box(ctx, image, zoom=zoom, focus=focus)

        scale = box.width() / image.width()
        rects = [
            ctx.to_pixels(line.bbox, line.page, scale, box.left(), box.top())
            for line in ctx.node.lines
            if line.page == page
        ]
        if not rects:
            return

        union = rects[0]
        for rect in rects[1:]:
            union = skia.Rect.MakeLTRB(
                min(union.left(), rect.left()),
                min(union.top(), rect.top()),
                max(union.right(), rect.right()),
                max(union.bottom(), rect.bottom()),
            )

        style.draw(
            selection.SelectionContext(
                canvas=ctx.canvas,
                lines=rects,
                union=union,
                brand=ctx.brand,
                rng=self.rng(ctx.cut.cut_id, style_name),
                progress=self._gesture_progress(t_local),
                elapsed=t_local,
                params=self.params,
            )
        )

    def _gesture_progress(self, t_local: float) -> float:
        """How far through *drawing* the selection we are.

        Deliberately not the shot's own progress. The shot is long because the
        clause has to stay on screen long enough to read (spec §4), but the
        gesture that points at it is a flick of a marker: it completes in about
        a second and then holds. Tying the two together would give a 58-word
        subsection a circle that takes twenty seconds to close.
        """
        draw_seconds = float(self.param("draw_seconds", 1.1))
        draw_seconds = max(0.05, min(draw_seconds, self.scene.dur))
        return max(0.0, min(1.0, t_local / draw_seconds))


class MarkerSweep(ClauseSelect):
    """Spec §5's named shot: the highlighter gesture."""

    name = "marker_sweep"
    default_style = "marker_sweep"


class UnderlineDraw(ClauseSelect):
    """Spec §5's named shot: the lighter alternative to a highlighter."""

    name = "underline_draw"
    default_style = "underline"


def _paper(ctx: RenderContext) -> int:
    from kifungu.render.text import color_of

    return color_of(ctx.brand.rgba("paper"))
