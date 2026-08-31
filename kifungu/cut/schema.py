"""The Cut — the storyboard IR (spec §4).

The contract between every front-end and the renderer. One file, one clip.

A Cut is deliberately small and readable: it holds the exact quoted string and
the exact citation, so it can be reviewed and approved *before* a frame is
rendered. This module defines its shape only. The accuracy guardrails of §8
live in `kifungu.cut.validate`, because some of them need the shot registry.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from kifungu import __version__

# Profiles that go in front of the public and therefore face the §8.7 gate.
PUBLIC_PROFILES = frozenset({"reel", "square", "portrait", "wide"})


class Source(BaseModel):
    doc_id: str
    title: str
    sha256: str
    citation: str
    page: int
    verbatim: str
    char_span: tuple[int, int] | None = None
    elided: bool = False
    emphasis: list[tuple[int, int]] = Field(default_factory=list)

    @field_validator("verbatim")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source.verbatim is empty — there is nothing to quote")
        return v

    @model_validator(mode="after")
    def _emphasis_in_range(self) -> Source:
        for start, end in self.emphasis:
            if not (0 <= start < end <= len(self.verbatim)):
                raise ValueError(
                    f"emphasis span ({start}, {end}) is outside verbatim "
                    f"of length {len(self.verbatim)}"
                )
        return self

    @property
    def word_count(self) -> int:
        return len(self.verbatim.split())


class Gloss(BaseModel):
    en: str = ""
    sw: str = ""
    approved_by: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.en.strip() or self.sw.strip())


class Audio(BaseModel):
    bed: str | None = None
    vo: str | None = None
    duck_db: float = -14.0


class Captions(BaseModel):
    burn_in: bool = False
    sidecar_srt: bool = True
    lang: str = "en"


class Scene(BaseModel):
    shot: str
    t_in: float
    dur: float
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("t_in")
    @classmethod
    def _t_in_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"scene t_in must be >= 0, got {v}")
        return v

    @field_validator("dur")
    @classmethod
    def _dur_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"scene dur must be > 0, got {v}")
        return v

    @property
    def t_out(self) -> float:
        return self.t_in + self.dur


class Cut(BaseModel):
    cut_id: str
    engine_version: str = Field(default_factory=lambda: __version__)
    created: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    operator: str = ""
    brand: str = "kdic"

    source: Source
    gloss: Gloss = Field(default_factory=Gloss)
    profiles: list[str] = Field(default_factory=lambda: ["reel"])
    audio: Audio = Field(default_factory=Audio)
    captions: Captions = Field(default_factory=Captions)
    scenes: list[Scene]

    @field_validator("cut_id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not v or any(ch.isspace() for ch in v):
            raise ValueError(f"cut_id must be a non-empty slug without spaces, got {v!r}")
        return v

    @field_validator("scenes")
    @classmethod
    def _at_least_one(cls, v: list[Scene]) -> list[Scene]:
        if not v:
            raise ValueError("a Cut needs at least one scene")
        return v

    @property
    def duration(self) -> float:
        """Total clip length. Scenes overlap deliberately (§4), so this is a max."""
        return max(scene.t_out for scene in self.scenes)

    def scenes_at(self, t: float) -> list[Scene]:
        return [s for s in self.scenes if s.t_in <= t < s.t_out]

    # ---- persistence --------------------------------------------------------

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads(self.model_dump_json())
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> Cut:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"no Cut at {path}")
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
