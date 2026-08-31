"""Brand tokens (spec §7).

Every colour, face and safe area comes from here. Nothing in the shot library
hard-codes a hex or a font name, so applying the real brand manual later is an
edit to one JSON file rather than a rebuild of the shot library.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from kifungu.platform import bundle_dir

RGBA = tuple[float, float, float, float]


class SafeArea(BaseModel):
    top: int
    bottom: int
    side: int


class Motion(BaseModel):
    default_ease: str = "out_quint"
    stagger: float = 0.12
    beat: float = 0.4


class Brand(BaseModel):
    name: str = "unnamed"
    provisional: bool = False
    colors: dict[str, str]
    type: dict[str, list[str]]
    logo: dict[str, str] = Field(default_factory=dict)
    safe_areas: dict[str, SafeArea] = Field(default_factory=dict)
    motion: Motion = Field(default_factory=Motion)

    @field_validator("colors")
    @classmethod
    def _validate_hexes(cls, v: dict[str, str]) -> dict[str, str]:
        for key, value in v.items():
            if not (value.startswith("#") and len(value) in (7, 9)):
                raise ValueError(f"colors.{key}: expected #RRGGBB or #RRGGBBAA, got {value!r}")
            int(value[1:], 16)  # raises on non-hex
        return v

    def rgba(self, token: str, alpha: float = 1.0) -> RGBA:
        """Resolve a colour token to premultiply-ready floats in 0..1."""
        try:
            raw = self.colors[token]
        except KeyError:
            raise KeyError(
                f"unknown colour token {token!r}; brand defines {sorted(self.colors)}"
            ) from None
        r = int(raw[1:3], 16) / 255.0
        g = int(raw[3:5], 16) / 255.0
        b = int(raw[5:7], 16) / 255.0
        a = int(raw[7:9], 16) / 255.0 if len(raw) == 9 else 1.0
        return (r, g, b, a * alpha)

    def families(self, role: str) -> list[str]:
        """Font stack for a type role ('display', 'body', 'mono', 'gloss')."""
        try:
            return list(self.type[role])
        except KeyError:
            raise KeyError(
                f"unknown type role {role!r}; brand defines {sorted(self.type)}"
            ) from None

    def safe_area(self, profile: str) -> SafeArea:
        if profile in self.safe_areas:
            return self.safe_areas[profile]
        # A missing safe area must not silently render ink to the edge.
        raise KeyError(f"brand defines no safe_area for profile {profile!r}")


def _search_paths(name: str) -> list[Path]:
    candidates = [Path.cwd() / "brand" / f"{name}.json", Path(name)]
    bundle = bundle_dir()
    if bundle is not None:
        candidates.insert(0, bundle / "brand" / f"{name}.json")
    # Repo layout: kifungu/brand.py -> ../brand/<name>.json
    candidates.append(Path(__file__).resolve().parent.parent / "brand" / f"{name}.json")
    return candidates


@lru_cache(maxsize=8)
def load_brand(name: str = "kdic") -> Brand:
    for path in _search_paths(name):
        if path.is_file():
            return Brand.model_validate(json.loads(path.read_text(encoding="utf-8")))
    tried = "\n  ".join(str(p) for p in _search_paths(name))
    raise FileNotFoundError(f"brand tokens {name!r} not found. Looked in:\n  {tried}")
