"""The shot library (spec §5).

The registry is the single source of truth for which shots exist, what they
require from the corpus, and which of them display text meant to be read —
which is what the hold-time rule in `cut.validate` checks against.
"""

from __future__ import annotations

from kifungu.render.shots.base import RenderContext, Shot
from kifungu.render.shots.citation_stamp import CitationStamp
from kifungu.render.shots.page_establish import PageEstablish
from kifungu.render.shots.spotlight import Spotlight

REGISTRY: dict[str, type[Shot]] = {
    PageEstablish.name: PageEstablish,
    Spotlight.name: Spotlight,
    CitationStamp.name: CitationStamp,
}

# Declared in the spec but not yet implemented. Named here so that authoring a
# Cut that uses one fails with "not implemented yet" rather than "unknown shot".
PLANNED: frozenset[str] = frozenset(
    {
        "scroll_hunt",
        "marker_sweep",
        "underline_draw",
        "clause_lift",
        "kinetic_typeset",
        "gloss_flip",
        "redaction_reveal",
        "key_figure",
        "endplate",
    }
)


def get(name: str) -> type[Shot]:
    if name in REGISTRY:
        return REGISTRY[name]
    if name in PLANNED:
        raise KeyError(
            f"shot {name!r} is in the spec but not implemented yet; "
            f"available now: {sorted(REGISTRY)}"
        )
    raise KeyError(f"unknown shot {name!r}; available: {sorted(REGISTRY)}")


__all__ = [
    "PLANNED",
    "REGISTRY",
    "CitationStamp",
    "PageEstablish",
    "RenderContext",
    "Shot",
    "Spotlight",
    "get",
]
