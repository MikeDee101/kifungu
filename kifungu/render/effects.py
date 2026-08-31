"""Image filters and masks (spec §5).

The shot library's gestures — a feathered spotlight, a lifted card over a
blurred page, motion-blur trails — are all filter work. Keeping them here means
a shot expresses *what* it wants ("dim everything except these lines, feathered
by 22px") rather than how the compositing is achieved.
"""

from __future__ import annotations

import skia

from kifungu.brand import RGBA
from kifungu.render.text import color_of


def paint(color: RGBA, *, anti_alias: bool = True) -> skia.Paint:
    return skia.Paint(Color=color_of(color), AntiAlias=anti_alias)


def blur_filter(sigma: float) -> skia.ImageFilter | None:
    return skia.ImageFilters.Blur(sigma, sigma) if sigma > 0 else None


def blur_paint(sigma: float, alpha: float = 1.0) -> skia.Paint:
    p = skia.Paint(AntiAlias=True)
    if sigma > 0:
        p.setImageFilter(skia.ImageFilters.Blur(sigma, sigma))
    p.setAlphaf(alpha)
    return p


def drop_shadow_paint(
    dx: float, dy: float, sigma: float, color: RGBA, alpha: float = 1.0
) -> skia.Paint:
    p = skia.Paint(AntiAlias=True)
    p.setImageFilter(skia.ImageFilters.DropShadow(dx, dy, sigma, sigma, color_of(color)))
    p.setAlphaf(alpha)
    return p


def rounded(rect: skia.Rect, radius: float) -> skia.RRect:
    return skia.RRect.MakeRectXY(rect, radius, radius)


def dim_except(
    canvas: skia.Canvas,
    width: float,
    height: float,
    holes: list[skia.Rect],
    color: RGBA,
    dim: float,
    feather_px: float,
    radius: float = 6.0,
) -> None:
    """Darken the frame except through feathered holes (the `spotlight` gesture).

    Drawn as one layer so the dim is uniform: painting per-hole would leave
    seams where holes overlap, which on adjacent text lines they always do.
    """
    if dim <= 0.0:
        return

    r, g, b, _ = color
    canvas.saveLayer(None, None)
    canvas.drawRect(skia.Rect.MakeWH(width, height), paint((r, g, b, dim)))

    if holes:
        cut = skia.Paint(AntiAlias=True)
        cut.setBlendMode(skia.BlendMode.kDstOut)
        if feather_px > 0:
            cut.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, feather_px / 3.0))
        cut.setColor(skia.ColorSetARGB(255, 0, 0, 0))
        for hole in holes:
            canvas.drawRRect(rounded(hole, radius), cut)

    canvas.restore()


def draw_image_fitted(
    canvas: skia.Canvas,
    image: skia.Image,
    dest: skia.Rect,
    *,
    paint_obj: skia.Paint | None = None,
) -> None:
    """Draw `image` into `dest` preserving aspect ratio (letterboxed, never squashed)."""
    scale = min(dest.width() / image.width(), dest.height() / image.height())
    w = image.width() * scale
    h = image.height() * scale
    x = dest.left() + (dest.width() - w) / 2.0
    y = dest.top() + (dest.height() - h) / 2.0
    canvas.drawImageRect(
        image,
        skia.Rect.MakeWH(image.width(), image.height()),
        skia.Rect.MakeXYWH(x, y, w, h),
        skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear),
        paint_obj,
    )
