"""Shot interface (spec §5).

Each shot is a class with `render(ctx, t_local)`, a declared z-order and a
declared set of required corpus artefacts. Adding a shot is the only way the
engine is meant to grow; nothing else should need editing.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

import skia

from kifungu.brand import Brand
from kifungu.corpus import BBox, Corpus, Node
from kifungu.render.profiles import Grid, Profile

if TYPE_CHECKING:
    from kifungu.cut.schema import Cut, Scene

# Decoded full-resolution pages held at once, and downscaled ones.
FULL_CACHE_LIMIT = 4
THUMB_CACHE_LIMIT = 24


@dataclass
class RenderContext:
    """Everything a shot may read while drawing one frame."""

    canvas: skia.Canvas
    profile: Profile
    grid: Grid
    brand: Brand
    cut: Cut
    corpus: Corpus | None
    t: float  # seconds from the start of the clip
    frame: int
    node: Node | None = None
    _images: dict[str, skia.Image] = field(default_factory=dict)

    def page_image(self, page: int) -> skia.Image:
        """Load a page raster, cached for the whole render (spec §6).

        The cache is bounded: a scroll through a 38-page Act at 300 DPI would
        otherwise hold a gigabyte of decoded rasters.
        """
        key = f"page:{page}"
        if key not in self._images:
            if self.corpus is None:
                raise ValueError("this shot needs a corpus, but none was loaded")
            path = self.corpus.page_raster(page)
            image = skia.Image.open(str(path))
            if image is None:
                raise ValueError(f"could not decode page raster {path}")
            self._evict(FULL_CACHE_LIMIT, "page:")
            self._images[key] = image
        return self._images[key]

    def page_thumb(self, page: int, max_px: int = 900) -> skia.Image:
        """A downscaled page, for shots that show many pages at once.

        `scroll_hunt` flies past pages far too fast for full resolution to be
        visible, and decoding them at full size is what would exhaust memory.
        """
        key = f"thumb:{page}:{max_px}"
        if key not in self._images:
            source = self.page_image(page)
            scale = min(1.0, max_px / max(source.width(), source.height()))
            width = max(1, int(source.width() * scale))
            height = max(1, int(source.height() * scale))
            surface = skia.Surface(width, height)
            with surface as canvas:
                canvas.clear(skia.ColorTRANSPARENT)
                canvas.drawImageRect(
                    source,
                    skia.Rect.MakeWH(source.width(), source.height()),
                    skia.Rect.MakeWH(width, height),
                    skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear),
                )
            self._evict(THUMB_CACHE_LIMIT, "thumb:")
            self._images[key] = surface.makeImageSnapshot()
        return self._images[key]

    def _evict(self, limit: int, prefix: str) -> None:
        keys = [k for k in self._images if k.startswith(prefix)]
        for key in keys[: max(0, len(keys) - limit + 1)]:
            del self._images[key]

    def to_pixels(self, bbox: BBox, page: int, scale: float, ox: float, oy: float) -> skia.Rect:
        """Convert a PDF-point bbox to frame pixels.

        Geometry is stored in points and converted here using the raster's
        actual scale (spec §3.1), so re-rastering at another DPI cannot
        misplace a highlight.
        """
        if self.corpus is None:
            raise ValueError("this shot needs a corpus, but none was loaded")
        geometry = self.corpus.page_geometry(page)
        k = geometry.scale * scale
        x0, y0, x1, y1 = bbox
        return skia.Rect.MakeLTRB(ox + x0 * k, oy + y0 * k, ox + x1 * k, oy + y1 * k)


class Shot:
    """Base class. Subclasses set the class vars and implement `render`."""

    name: ClassVar[str] = "shot"
    z_order: ClassVar[int] = 0
    requires: ClassVar[frozenset[str]] = frozenset()
    # Whether this shot puts text on screen to be *read*, which triggers the
    # hold-time rule of spec §4. A page raster is not reading text; re-typeset
    # statutory text is.
    displays_reading_text: ClassVar[bool] = False

    def __init__(self, scene: Scene) -> None:
        self.scene = scene
        self.params: dict[str, Any] = dict(scene.params)

    def param(self, key: str, default: Any) -> Any:
        return self.params.get(key, default)

    def rng(self, cut_id: str, salt: str = "") -> random.Random:
        """Deterministic jitter, seeded from the cut_id (spec §6).

        A re-render after a copy edit must match frame for frame, so no shot
        may use unseeded randomness.
        """
        seed = hashlib.sha256(f"{cut_id}:{self.name}:{salt}".encode()).digest()
        return random.Random(int.from_bytes(seed[:8], "big"))

    def render(self, ctx: RenderContext, t_local: float) -> None:
        raise NotImplementedError

    def progress(self, t_local: float) -> float:
        return max(0.0, min(1.0, t_local / self.scene.dur)) if self.scene.dur > 0 else 1.0


# Fraction of the page box a drop shadow can extend beyond its edges, given the
# shadow parameters used by page_establish.
SHADOW_EXTENT = 0.06


def page_box(
    ctx: RenderContext,
    image: skia.Image,
    *,
    zoom: float = 1.0,
    focus: tuple[float, float] = (0.5, 0.5),
    drift: float = 0.0,
    shadow: bool = False,
) -> skia.Rect:
    """Frame a page, optionally pushed in on a point.

    `focus` is normalised page coordinates (0..1). At zoom 1.0 with a centred
    focus this is exactly `fitted_page_box`, so a shot can push in from the
    established framing without the page appearing to jump.
    """
    base = fitted_page_box(ctx, image, drift=drift, shadow=shadow)
    width = base.width() * zoom
    height = base.height() * zoom
    fx, fy = focus
    x = ctx.grid.center_x - fx * width
    y = ctx.grid.center_y - fy * height

    # Clamp the camera so a page large enough to cover the frame never reveals
    # its own edge. Without this, focusing on a clause near the foot of a page
    # slides the paper up and leaves bare ground in the bottom of the shot.
    if width >= ctx.profile.width:
        x = min(0.0, max(x, ctx.profile.width - width))
    if height >= ctx.profile.height:
        y = min(0.0, max(y, ctx.profile.height - height))

    return skia.Rect.MakeXYWH(x, y, width, height)


def focus_of(ctx: RenderContext, node, page: int) -> tuple[float, float]:
    """Normalised page coordinates of a node's centre on `page`, for zoom targets."""
    if node is None or ctx.corpus is None:
        return (0.5, 0.5)
    box = node.page_bbox(page)
    if box is None:
        return (0.5, 0.5)
    geometry = ctx.corpus.page_geometry(page)
    x0, y0, x1, y1 = box
    return (
        min(1.0, max(0.0, ((x0 + x1) / 2.0) / geometry.width_pt)),
        min(1.0, max(0.0, ((y0 + y1) / 2.0) / geometry.height_pt)),
    )


def fitted_page_box(
    ctx: RenderContext, image: skia.Image, *, drift: float = 0.0, shadow: bool = False
) -> skia.Rect:
    """Fit a page raster inside the safe area, centred on the grid.

    Headroom is reserved for the drift scale and for the drop shadow, because
    both extend past the fitted box and no ink may leave the safe area (§6).
    Both page shots call this, so the page cannot jump between them.
    """
    grid = ctx.grid
    shrink = (1.0 + max(0.0, drift)) * (1.0 + (SHADOW_EXTENT if shadow else 0.0))
    scale = min(
        grid.content_width / image.width(), grid.content_height / image.height()
    ) / shrink
    w = image.width() * scale
    h = image.height() * scale
    return skia.Rect.MakeXYWH(grid.center_x - w / 2.0, grid.center_y - h / 2.0, w, h)
