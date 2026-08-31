"""Accuracy and approvals guardrails (spec §8).

This engine quotes an Act of Parliament on public channels under the
Corporation's name. These checks are part of the spec, not a nicety, so they
run before a single frame is drawn rather than as a review convention.
"""

from __future__ import annotations

from dataclasses import dataclass

from kifungu.corpus import Corpus
from kifungu.cut.schema import PUBLIC_PROFILES, Cut
from kifungu.render.shots import PLANNED, REGISTRY

ELLIPSIS = "\u2026"


@dataclass
class Problem:
    level: str  # "error" | "warning"
    rule: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.rule}: {self.message}"


class ValidationError(Exception):
    def __init__(self, problems: list[Problem]) -> None:
        self.problems = problems
        super().__init__("\n".join(str(p) for p in problems))


def hold_time_required(word_count: int) -> float:
    """Spec §4 — legal English at six seconds is unreadable."""
    return max(1.8, 0.35 * word_count + 0.8)


def validate(
    cut: Cut,
    corpus: Corpus | None = None,
    *,
    strict: bool = False,
    draft: bool = False,
    profiles: list[str] | None = None,
) -> list[Problem]:
    problems: list[Problem] = []
    targets = profiles if profiles is not None else cut.profiles
    public = [p for p in targets if p in PUBLIC_PROFILES]

    _check_shots(cut, problems)
    _check_hold_times(cut, problems)
    _check_verbatim(cut, corpus, problems)
    _check_elision(cut, problems, strict)
    _check_citation(cut, problems, public)
    _check_gloss_gate(cut, problems, public, draft)

    return problems


def raise_for(problems: list[Problem]) -> None:
    errors = [p for p in problems if p.level == "error"]
    if errors:
        raise ValidationError(errors)


# ---- individual rules -------------------------------------------------------


def _check_shots(cut: Cut, problems: list[Problem]) -> None:
    for scene in cut.scenes:
        if scene.shot in REGISTRY:
            continue
        detail = (
            "is in the spec but not implemented yet"
            if scene.shot in PLANNED
            else f"is unknown; available: {sorted(REGISTRY)}"
        )
        problems.append(Problem("error", "shot", f"{scene.shot!r} {detail}"))


def _check_hold_times(cut: Cut, problems: list[Problem]) -> None:
    words = cut.source.word_count
    gloss_words = len((cut.gloss.en or "").split())
    for scene in cut.scenes:
        shot = REGISTRY.get(scene.shot)
        if shot is None or not shot.displays_reading_text:
            continue
        count = gloss_words if scene.shot == "gloss_flip" else words
        needed = hold_time_required(count)
        if scene.dur + 1e-6 < needed:
            problems.append(
                Problem(
                    "error",
                    "hold_time",
                    f"{scene.shot} holds {count} words for {scene.dur:.2f}s; "
                    f"needs >= {needed:.2f}s to be readable",
                )
            )


def _check_verbatim(cut: Cut, corpus: Corpus | None, problems: list[Problem]) -> None:
    if corpus is None:
        problems.append(
            Problem("warning", "verbatim", "no corpus supplied; verbatim lock was not checked")
        )
        return

    if cut.source.sha256 and corpus.meta.sha256 != cut.source.sha256:
        problems.append(
            Problem(
                "error",
                "source_pinning",
                f"this Cut was authored against source sha256 {cut.source.sha256[:12]}… "
                f"but the corpus now holds {corpus.meta.sha256[:12]}…. "
                "The document changed — re-author the Cut against the new text.",
            )
        )
        return

    span = cut.source.char_span
    if span is None:
        problems.append(
            Problem("warning", "verbatim", "Cut has no char_span; verbatim lock cannot be checked")
        )
        return

    actual = corpus.full_text[span[0] : span[1]]
    if actual != cut.source.verbatim:
        problems.append(
            Problem(
                "error",
                "verbatim_lock",
                "source.verbatim does not match the document at char_span "
                f"{span}. Expected {actual[:60]!r}, Cut says {cut.source.verbatim[:60]!r}. "
                "Quoted text is never hand-edited: re-author the Cut instead.",
            )
        )


def _check_elision(cut: Cut, problems: list[Problem], strict: bool) -> None:
    has_ellipsis = ELLIPSIS in cut.source.verbatim
    if has_ellipsis and not cut.source.elided:
        problems.append(
            Problem(
                "error",
                "elision",
                f"verbatim contains '{ELLIPSIS}' but elided is false — "
                "trimming must be declared",
            )
        )
    if strict and (cut.source.elided or has_ellipsis):
        problems.append(
            Problem("error", "elision", "--strict refuses to render elided quotes")
        )


def _check_citation(cut: Cut, problems: list[Problem], public: list[str]) -> None:
    if not public:
        return
    if not cut.source.citation.strip():
        problems.append(Problem("error", "citation", "source.citation is empty"))
    if not any(scene.shot == "citation_stamp" for scene in cut.scenes):
        problems.append(
            Problem(
                "error",
                "citation",
                f"public profiles {public} require a citation_stamp scene "
                "(document short title and year included)",
            )
        )


def _check_gloss_gate(
    cut: Cut, problems: list[Problem], public: list[str], draft: bool
) -> None:
    if not public or draft:
        return
    uses_gloss = any(scene.shot == "gloss_flip" for scene in cut.scenes)
    if not uses_gloss and cut.gloss.is_empty:
        return
    if cut.gloss.approved_by is None:
        problems.append(
            Problem(
                "error",
                "approval_gate",
                f"public profiles {public} refuse to render while gloss.approved_by is null. "
                "Use --draft or the broll profile for internal iteration.",
            )
        )
