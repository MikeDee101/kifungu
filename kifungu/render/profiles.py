"""Output profiles and the safe-area system (spec §6).

Layout adapts per profile *against a grid*, never by scaling: a 16:9 frame
cropped to 9:16 loses the composition. Each profile declares its dimensions and
the brand declares its margins; shots lay out inside the resulting content box.
"""

from __future__ import annotations

from dataclasses import dataclass

from kifungu.brand import Brand


@dataclass(frozen=True)
class Profile:
    name: str
    width: int
    height: int
    fps: int = 30
    codec: str = "h264"
    pix_fmt: str = "yuv420p"
    container: str = "mp4"
    alpha: bool = False
    public: bool = True
    png_sequence: bool = False

    @property
    def is_draft(self) -> bool:
        return self.name.endswith("@draft")


PROFILES: dict[str, Profile] = {
    "reel": Profile("reel", 1080, 1920),
    "square": Profile("square", 1080, 1080),
    "portrait": Profile("portrait", 1080, 1350),
    "wide": Profile("wide", 1920, 1080),
    # A keyable element for After Effects / Premiere: a genuine alpha channel,
    # not a black matte, and stripped of endplate, captions and background.
    "broll": Profile(
        "broll",
        1920,
        1080,
        codec="prores_ks",
        pix_fmt="yuva444p10le",
        container="mov",
        alpha=True,
        public=False,
        png_sequence=True,
    ),
}


def get(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError:
        raise KeyError(f"unknown profile {name!r}; available: {sorted(PROFILES)}") from None


def draft(profile: Profile) -> Profile:
    """Half-ish resolution at 15fps for approval loops (spec §9)."""
    scale = 540.0 / min(profile.width, profile.height)
    even = lambda v: int(round(v * scale)) // 2 * 2  # noqa: E731 - encoders need even dims
    return Profile(
        name=f"{profile.name}@draft",
        width=even(profile.width),
        height=even(profile.height),
        fps=15,
        codec=profile.codec,
        pix_fmt=profile.pix_fmt,
        container=profile.container,
        alpha=profile.alpha,
        public=profile.public,
        png_sequence=False,
    )


@dataclass(frozen=True)
class Grid:
    """The content box a shot may draw into, plus title/body/footer bands."""

    width: int
    height: int
    left: float
    top: float
    right: float
    bottom: float

    @property
    def content_width(self) -> float:
        return self.right - self.left

    @property
    def content_height(self) -> float:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2.0

    def band(self, start: float, end: float) -> tuple[float, float]:
        """A horizontal band as (y0, y1), given fractions of the content height."""
        return (
            self.top + self.content_height * start,
            self.top + self.content_height * end,
        )


def grid_for(profile: Profile, brand: Brand) -> Grid:
    base = profile.name.split("@", 1)[0]
    safe = brand.safe_area(base)
    scale = profile.width / PROFILES[base].width if base in PROFILES else 1.0
    side = safe.side * scale
    return Grid(
        width=profile.width,
        height=profile.height,
        left=side,
        top=safe.top * scale,
        right=profile.width - side,
        bottom=profile.height - safe.bottom * scale,
    )
