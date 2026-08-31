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
        """Load a page raster, cached for the whole render (spec §6)."""
        key = f"page:{page}"
        if key not in self._images:
            if self.corpus is None:
                raise ValueError("this shot needs a corpus, but none was loaded")
            path = self.corpus.page_raster(page)
            image = skia.Image.open(str(path))
            if image is None:
                raise ValueError(f"could not decode page raster {path}")
            self._images[key] = image
        return self._images[key]

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
