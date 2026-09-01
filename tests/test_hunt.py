"""The hunt: scroll from the cover, push in, and point at the clause."""

from __future__ import annotations

import numpy as np
import pytest
import skia

from kifungu.brand import load_brand
from kifungu.corpus import Corpus
from kifungu.cut.schema import Scene
from kifungu.cut.templates import cut_from_template
from kifungu.render import compositor
from kifungu.render import profiles as profile_module
from kifungu.render.selection import STYLES
from kifungu.render.selection import get as get_style
from kifungu.render.shots import get as get_shot
from kifungu.render.shots.base import page_box
from kifungu.render.shots.clause_zoom import clause_zoom_factor

pytestmark = pytest.mark.render


@pytest.fixture(scope="module")
def brand():
    return load_brand("kdic")


@pytest.fixture(scope="module")
def hunt(corpus: Corpus):
    return cut_from_template(corpus, "s.12(1)", "clause_hunt")


def frame(cut, corpus, brand, profile, t):
    shots = [(get_shot(s.shot)(s), s) for s in cut.scenes]
    surface = skia.Surface(profile.width, profile.height)
    with surface as canvas:
        compositor.render_frame(canvas, cut, corpus, profile, brand, t, 0, shots, {})
    snapshot = surface.makeImageSnapshot()
    return (
        np.frombuffer(compositor._rgba_bytes(snapshot, profile), dtype=np.uint8)
        .reshape(profile.height, profile.width, 4)
        .copy()
    )


# ---- scroll_hunt -----------------------------------------------------------


def test_scroll_opens_on_the_cover():
    """The gesture is meaningless if the Act's cover is never actually seen."""
    shot = get_shot("scroll_hunt")(Scene(shot="scroll_hunt", t_in=0, dur=2.2, params={}))
    assert shot._position(0.0, 1, 16, "out_quint") == pytest.approx(1.0)
    # Still on the cover through the opening hold.
    assert shot._position(0.3, 1, 16, "out_quint") == pytest.approx(1.0)


def test_scroll_lands_exactly_on_the_target():
    shot = get_shot("scroll_hunt")(Scene(shot="scroll_hunt", t_in=0, dur=2.2, params={}))
    assert shot._position(2.2, 1, 16, "out_quint") == pytest.approx(16.0, abs=1e-6)


def test_scroll_decelerates():
    """Fast at the top, nearly stationary at the landing."""
    shot = get_shot("scroll_hunt")(Scene(shot="scroll_hunt", t_in=0, dur=2.2, params={}))
    early = abs(shot._velocity(0.6, 1, 30, "out_quint"))
    late = abs(shot._velocity(2.1, 1, 30, "out_quint"))
    assert early > late * 4


# ---- geometry of a clause that crosses a page break -------------------------


def test_page_bbox_never_spans_two_pages(corpus: Corpus):
    """A union across pages describes a rectangle that exists on neither."""
    for node in corpus.nodes.values():
        pages = {line.page for line in node.lines}
        if len(pages) < 2:
            continue
        for page in pages:
            box = node.page_bbox(page)
            assert box is not None
            on_page = [line.bbox for line in node.lines if line.page == page]
            assert box[1] >= min(b[1] for b in on_page) - 1e-6
            assert box[3] <= max(b[3] for b in on_page) + 1e-6
        break


def test_dominant_page_is_where_most_of_the_clause_is(corpus: Corpus):
    node = corpus.by_citation("s.12(1)")
    counts: dict[int, int] = {}
    for line in node.lines:
        counts[line.page] = counts.get(line.page, 0) + 1
    assert node.dominant_page == max(counts, key=lambda p: counts[p])


# ---- the camera -------------------------------------------------------------


def test_zoom_pushes_in_on_the_clause(corpus, hunt, brand):
    profile = profile_module.get("reel")
    shots = [(get_shot(s.shot)(s), s) for s in hunt.scenes]
    surface = skia.Surface(profile.width, profile.height)
    with surface as canvas:
        ctx = compositor.build_context(canvas, hunt, corpus, profile, brand, 0.0, 0, shots)
    image = ctx.page_image(ctx.node.dominant_page)
    assert clause_zoom_factor(ctx, image, ctx.node.dominant_page) > 1.0


def test_zoomed_page_covers_the_frame(corpus, hunt, brand):
    """A zoomed plate must never reveal its own edge (camera clamping)."""
    profile = profile_module.get("reel")
    shots = [(get_shot(s.shot)(s), s) for s in hunt.scenes]
    surface = skia.Surface(profile.width, profile.height)
    with surface as canvas:
        ctx = compositor.build_context(canvas, hunt, corpus, profile, brand, 0.0, 0, shots)
    image = ctx.page_image(ctx.node.dominant_page)
    box = page_box(ctx, image, zoom=3.0, focus=(0.5, 0.95))
    assert box.left() <= 0 and box.right() >= profile.width
    assert box.top() <= 0 and box.bottom() >= profile.height


# ---- selection styles -------------------------------------------------------


@pytest.mark.parametrize("style", sorted(STYLES))
def test_every_style_marks_the_page(corpus, hunt, brand, style):
    """A style that draws nothing visible is worse than no style."""
    profile = profile_module.get("reel")
    select_at = next(s.t_in for s in hunt.scenes if s.shot == "clause_select")

    marked = hunt.model_copy(deep=True)
    for scene in marked.scenes:
        if scene.shot == "clause_select":
            scene.params["style"] = style
    bare = hunt.model_copy(deep=True)
    bare.scenes = [s for s in bare.scenes if s.shot != "clause_select"]

    t = select_at + 1.4
    a = frame(marked, corpus, brand, profile, t).astype(np.int16)
    b = frame(bare, corpus, brand, profile, t).astype(np.int16)
    changed = (np.abs(a - b).sum(axis=2) > 20).mean()
    assert changed > 0.002, f"{style} changed only {changed:.4%} of the frame"


def test_unknown_style_is_rejected_at_authoring(corpus: Corpus):
    with pytest.raises(KeyError, match="unknown selection style"):
        cut_from_template(corpus, "s.12(1)", "clause_hunt", style="sharpie")


def test_styles_are_deterministic(corpus, hunt, brand):
    """Seeded jitter only — a re-render after a copy edit must match."""
    profile = profile_module.get("square")
    t = next(s.t_in for s in hunt.scenes if s.shot == "clause_select") + 0.5
    first = frame(hunt, corpus, brand, profile, t)
    second = frame(hunt, corpus, brand, profile, t)
    assert np.array_equal(first, second)


def test_gesture_finishes_well_before_a_long_hold(corpus: Corpus):
    """A 21-second hold must not mean a 21-second circle."""
    scene = Scene(shot="clause_select", t_in=0.0, dur=21.0, params={})
    shot = get_shot("clause_select")(scene)
    assert shot._gesture_progress(1.2) == pytest.approx(1.0)
    assert shot._gesture_progress(0.55) < 1.0


def test_style_registry_descriptions_are_present():
    for name, style in STYLES.items():
        assert style.description.strip(), f"{name} has no description for `kifungu styles`"
        assert get_style(name).name == name


def test_marquee_ants_keep_marching_during_the_hold(corpus, hunt, brand):
    """The dashes animate with elapsed time, not with the draw progress."""
    profile = profile_module.get("square")
    marched = hunt.model_copy(deep=True)
    for scene in marched.scenes:
        if scene.shot == "clause_select":
            scene.params["style"] = "marquee"
    select_at = next(s.t_in for s in marched.scenes if s.shot == "clause_select")

    # Both well past the point where the box has finished growing.
    a = frame(marched, corpus, brand, profile, select_at + 3.0)
    b = frame(marched, corpus, brand, profile, select_at + 3.25)
    assert not np.array_equal(a, b), "the ants stopped moving once the gesture completed"
