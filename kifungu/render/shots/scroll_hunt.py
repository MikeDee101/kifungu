"""`scroll_hunt` — the "searching the law" gesture (spec §5).

Opens on the cover of the Act and races down through the pages, decelerating
onto the one holding the clause. Pages blur as they fly past and settle as the
scroll slows, so the motion reads as a hand hunting through a statute rather
than a slideshow advancing.

Speed comes from easing, not from frame skipping: the position curve is
`out_quint` over the whole shot, which is fast at the top and almost stationary
at the landing. Blur is derived from the frame-to-frame velocity of that same
curve, so the two can never disagree.
"""

from __future__ import annotations

import skia

from kifungu.render.easing import get as ease
from kifungu.render.shots.base import RenderContext, Shot, fitted_page_box

# Vertical gap between pages, as a fraction of page height.
GAP = 0.06
# Velocity (pages per second) at which the trail blur reaches full strength.
BLUR_REFERENCE = 9.0
MAX_BLUR_PX = 26.0


class ScrollHunt(Shot):
    name = "scroll_hunt"
    z_order = 5
    requires = frozenset({"page_raster"})

    def render(self, ctx: RenderContext, t_local: float) -> None:
        target = int(self.param("to_page", ctx.node.dominant_page if ctx.node else 1))
        start = int(self.param("from_page", 1))
        easing = str(self.param("ease", "out_quint"))
        blur_trail = bool(self.param("blur_trail", True))
        thumb_px = int(self.param("thumb_px", 900))

        position = self._position(t_local, start, target, easing)
        velocity = self._velocity(t_local, start, target, easing)

        image = ctx.page_thumb(max(1, min(target, self._last_page(ctx))), thumb_px)
        base = fitted_page_box(ctx, image, shadow=True)
        stride = base.height() * (1.0 + GAP)

        blur = 0.0
        if blur_trail:
            blur = min(MAX_BLUR_PX, MAX_BLUR_PX * abs(velocity) / BLUR_REFERENCE)

        paint = skia.Paint(AntiAlias=True)
        if blur > 0.4:
            paint.setImageFilter(skia.ImageFilters.Blur(blur * 0.35, blur))

        last = self._last_page(ctx)
        current = int(round(position))
        for page in range(current - 1, current + 2):
            if not 1 <= page <= last:
                continue
            offset = (page - position) * stride
            rect = skia.Rect.MakeXYWH(
                base.left(), base.top() + offset, base.width(), base.height()
            )
            if rect.bottom() < 0 or rect.top() > ctx.profile.height:
                continue
            ctx.canvas.drawImageRect(
                ctx.page_thumb(page, thumb_px),
                skia.Rect.MakeWH(image.width(), image.height()),
                rect,
                skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear),
                paint,
            )

    # ---- the scroll curve ---------------------------------------------------

    def _position(self, t_local: float, start: int, target: int, easing: str) -> float:
        # An out_quint is at its fastest immediately, so without a beat on the
        # cover the Act is never actually seen: the title page would be gone
        # within two frames. Hold, then go.
        hold = float(self.param("hold_start", 0.45))
        if self.scene.dur <= hold:
            return float(start)
        p = max(0.0, min(1.0, (t_local - hold) / (self.scene.dur - hold)))
        return start + (target - start) * ease(easing)(p)

    def _velocity(self, t_local: float, start: int, target: int, easing: str) -> float:
        """Pages per second, by difference — the curve has no analytic form here."""
        dt = 1.0 / 60.0
        ahead = self._position(t_local + dt, start, target, easing)
        behind = self._position(max(0.0, t_local - dt), start, target, easing)
        return (ahead - behind) / (2.0 * dt)

    @staticmethod
    def _last_page(ctx: RenderContext) -> int:
        return ctx.corpus.meta.page_count if ctx.corpus is not None else 1
