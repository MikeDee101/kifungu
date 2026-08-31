"""Cut authoring from templates (spec §4.1).

Templates are parameterised scene lists in YAML. Two conventions make them
robust:

* ``overlap`` positions a scene relative to the end of the previous one, so
  scenes overlap by construction — that overlap is what makes the result read
  as motion design rather than a slideshow (§4).
* ``dur: auto`` derives a hold from the clause's own word count via the
  hold-time rule. Hard-coding seconds in a template is how you end up with
  legal English on screen for four seconds; deriving them means a longer
  clause simply gets a longer hold.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from kifungu.corpus import Corpus
from kifungu.cut.schema import Cut, Scene, Source
from kifungu.cut.validate import hold_time_required
from kifungu.platform import bundle_dir


class TemplateScene(BaseModel):
    shot: str
    dur: float | str = "auto"
    overlap: float = 0.0
    params: dict = Field(default_factory=dict)


class Template(BaseModel):
    name: str
    description: str = ""
    profiles: list[str] = Field(default_factory=lambda: ["reel"])
    scenes: list[TemplateScene]

    def build_scenes(self, word_count: int, gloss_words: int = 0) -> list[Scene]:
        scenes: list[Scene] = []
        cursor = 0.0
        for entry in self.scenes:
            t_in = max(0.0, cursor - entry.overlap) if scenes else 0.0
            if isinstance(entry.dur, str):
                if entry.dur != "auto":
                    raise ValueError(
                        f"scene {entry.shot!r}: dur must be a number or 'auto', got {entry.dur!r}"
                    )
                count = gloss_words if entry.shot == "gloss_flip" else word_count
                dur = round(hold_time_required(count), 2)
            else:
                dur = float(entry.dur)
            scenes.append(Scene(shot=entry.shot, t_in=round(t_in, 2), dur=dur, params=entry.params))
            cursor = t_in + dur
        return scenes


def _search_paths(name: str) -> list[Path]:
    candidates = [Path.cwd() / "templates" / f"{name}.yaml", Path(name)]
    bundle = bundle_dir()
    if bundle is not None:
        candidates.insert(0, bundle / "templates" / f"{name}.yaml")
    candidates.append(Path(__file__).resolve().parents[2] / "templates" / f"{name}.yaml")
    return candidates


def load_template(name: str) -> Template:
    for path in _search_paths(name):
        if path.is_file():
            return Template.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    tried = "\n  ".join(str(p) for p in _search_paths(name))
    raise FileNotFoundError(f"template {name!r} not found. Looked in:\n  {tried}")


def available_templates() -> list[str]:
    seen: dict[str, None] = {}
    for base in {p.parent for p in _search_paths("_")}:
        if base.is_dir():
            for path in sorted(base.glob("*.yaml")):
                seen.setdefault(path.stem, None)
    return list(seen)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "cut"


def cut_from_template(
    corpus: Corpus,
    citation: str,
    template_name: str,
    *,
    profiles: list[str] | None = None,
    operator: str = "",
    cut_id: str | None = None,
    brand: str = "kdic",
) -> Cut:
    node = corpus.by_citation(citation)
    template = load_template(template_name)

    source = Source(
        doc_id=corpus.meta.doc_id,
        title=corpus.meta.title,
        sha256=corpus.meta.sha256,
        citation=node.citation,
        page=node.page,
        # Exactly the source substring. Tidying whitespace here would break the
        # verbatim lock, which is the point of the lock.
        verbatim=node.text,
        char_span=node.char_span,
    )

    identifier = cut_id or slugify(f"{corpus.meta.doc_id}-{node.citation}-{template.name}")
    return Cut(
        cut_id=identifier,
        operator=operator,
        brand=brand,
        source=source,
        profiles=profiles or template.profiles,
        scenes=template.build_scenes(source.word_count),
    )
