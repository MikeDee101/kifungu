"""Render-side tests: playback compatibility, determinism, alpha and safe areas (spec §13)."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
import skia

from kifungu.brand import load_brand
from kifungu.corpus import Corpus
from kifungu.cut.templates import cut_from_template
from kifungu.render import compositor, encode
from kifungu.render import profiles as profile_module
from kifungu.render.easing import EASINGS, get
from kifungu.render.profiles import draft, grid_for
from kifungu.render.text import TextSpec, measure

pytestmark = pytest.mark.render


@pytest.fixture(scope="module")
def brand():
    return load_brand("kdic")


@pytest.fixture(scope="module")
def cut(corpus: Corpus):
    return cut_from_template(corpus, "s.12(1)", "clause_spotlight")


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- playback compatibility (§6, §13) --------------------------------------


def test_h264_output_is_yuv420p(corpus, cut, brand, tmp_path):
    """Without yuv420p the file will not play in browsers, WhatsApp or PowerPoint."""
    profile = draft(profile_module.get("reel"))
    result = compositor.render(cut, corpus, profile, tmp_path, brand)
    assert result.path.exists()
    assert encode.probe_pix_fmt(result.path) == "yuv420p"


def test_render_is_deterministic(corpus, cut, brand, tmp_path):
    profile = draft(profile_module.get("square"))
    first = compositor.render(cut, corpus, profile, tmp_path / "a", brand)
    second = compositor.render(cut, corpus, profile, tmp_path / "b", brand)
    assert sha256(first.path) == sha256(second.path)


def test_broll_carries_genuine_transparency(corpus, cut, brand, tmp_path):
    """A black matte is not an alpha channel (spec §6)."""
    profile = profile_module.get("broll")
    frames = _frames(cut, corpus, profile, brand, count=1)
    alpha = frames[0][:, :, 3]
    assert alpha.min() == 0, "no transparent pixels — the element is not keyable"
    assert alpha.max() == 255, "no opaque pixels — nothing was drawn"
    transparent = float((alpha < 8).mean())
    assert 0.05 < transparent < 0.95, f"implausible transparency ratio {transparent:.2f}"


# ---- safe areas (§6, §13) --------------------------------------------------


def test_no_ink_outside_the_safe_area(corpus, cut, brand):
    """Nothing may be drawn outside the profile's declared safe area."""
    profile = profile_module.get("reel")
    grid = grid_for(profile, brand)
    frame = _frames(cut, corpus, profile, brand, count=1, at=0.6)[0]

    ground = np.array(_rgba(brand.rgba("paper")), dtype=np.int16)
    difference = np.abs(frame.astype(np.int16) - ground).sum(axis=2)
    ink = difference > 24

    top = int(grid.top)
    bottom = int(grid.bottom)
    left = int(grid.left)
    right = int(grid.right)
    assert not ink[:top, :].any(), "ink above the safe area"
    assert not ink[bottom:, :].any(), "ink below the safe area"
    assert not ink[:, :left].any(), "ink left of the safe area"
    assert not ink[:, right:].any(), "ink right of the safe area"


# ---- easing ----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EASINGS))
def test_easings_are_normalised(name):
    fn = get(name)
    assert fn(0.0) == pytest.approx(0.0, abs=1e-6)
    assert fn(1.0) == pytest.approx(1.0, abs=1e-6)


def test_out_back_overshoots():
    assert max(get("out_back")(t / 100) for t in range(101)) > 1.0


# ---- typesetting -----------------------------------------------------------


def test_text_wraps_and_grows_with_content(brand):
    spec = TextSpec(
        text="The Corporation shall pay to every depositor of an institution. " * 4,
        families=brand.families("body"),
        size=32,
        color=brand.rgba("ink"),
    )
    narrow, _ = measure(spec, 300)
    wide, _ = measure(spec, 900)
    assert narrow > wide > 0


def test_kiswahili_and_diacritics_shape(brand):
    """Kiswahili glosses and Kenyan orthographies must not fall back to boxes."""
    spec = TextSpec(
        text="Benki ikifungwa, KDIC inakurudishia pesa zako — hadi shilingi 500,000. ĩ",
        families=brand.families("body"),
        size=28,
        color=brand.rgba("ink"),
    )
    height, longest = measure(spec, 800)
    assert height > 0 and longest > 0


def test_emphasis_spans_do_not_change_the_text(brand):
    plain = TextSpec(text="one two three", families=brand.families("body"), size=24,
                     color=brand.rgba("ink"))
    marked = TextSpec(text="one two three", families=brand.families("body"), size=24,
                      color=brand.rgba("ink"), emphasis=[(4, 7)],
                      emphasis_color=brand.rgba("accent"))
    assert measure(plain, 400)[0] == pytest.approx(measure(marked, 400)[0], abs=1.0)


# ---- helpers ---------------------------------------------------------------


def _rgba(rgba):
    return [int(round(c * 255)) for c in rgba]


def _frames(cut, corpus, profile, brand, count=1, at=None):
    """Render frames straight to numpy, bypassing ffmpeg."""
    shots = [(compositor.get_shot(scene.shot)(scene), scene) for scene in cut.scenes]
    surface = skia.Surface(profile.width, profile.height)
    images = {}
    out = []
    for index in range(count):
        t = at if at is not None else index / profile.fps
        with surface as canvas:
            compositor.render_frame(
                canvas, cut, corpus, profile, brand, t, index, shots, images
            )
        snapshot = surface.makeImageSnapshot()
        out.append(np.frombuffer(compositor._rgba_bytes(snapshot, profile), dtype=np.uint8)
                   .reshape(profile.height, profile.width, 4).copy())
    return out
