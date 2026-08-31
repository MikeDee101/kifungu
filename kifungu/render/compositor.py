"""The frame loop (spec §6).

Scenes overlap deliberately, so every frame asks which scenes are live and
draws them in z-order. That overlap is what makes the result read as motion
design rather than a slideshow.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import skia

from kifungu.brand import Brand, load_brand
from kifungu.corpus import Corpus
from kifungu.cut.schema import Cut
from kifungu.render import encode
from kifungu.render.profiles import Profile, grid_for
from kifungu.render.shots import RenderContext
from kifungu.render.shots import get as get_shot
from kifungu.render.text import color_of


@dataclass
class RenderResult:
    profile: str
    path: Path
    frames: int
    duration: float
    srt: Path | None = None


def _surface(profile: Profile) -> skia.Surface:
    # Always render with alpha; profiles without it are flattened by the encoder.
    return skia.Surface(profile.width, profile.height)


def render_frame(
    canvas: skia.Canvas,
    cut: Cut,
    corpus: Corpus | None,
    profile: Profile,
    brand: Brand,
    t: float,
    frame_index: int,
    shots: list,
    images: dict,
) -> None:
    node = None
    if corpus is not None and cut.source.citation:
        try:
            node = corpus.by_citation(cut.source.citation)
        except KeyError:
            node = None

    if profile.alpha:
        # A keyable element must start genuinely transparent, not on a matte.
        canvas.clear(skia.ColorTRANSPARENT)
    else:
        # The brand ground, not white: shots that run after page_establish has
        # ended would otherwise dim a white frame to grey.
        canvas.clear(color_of(brand.rgba("paper")))

    ctx = RenderContext(
        canvas=canvas,
        profile=profile,
        grid=grid_for(profile, brand),
        brand=brand,
        cut=cut,
        corpus=corpus,
        t=t,
        frame=frame_index,
        node=node,
        _images=images,
    )

    live = [(shot, scene) for shot, scene in shots if scene.t_in <= t < scene.t_out]
    for shot, scene in sorted(live, key=lambda pair: pair[0].z_order):
        canvas.save()
        try:
            shot.render(ctx, t - scene.t_in)
        finally:
            canvas.restore()


def render(
    cut: Cut,
    corpus: Corpus | None,
    profile: Profile,
    out_dir: Path,
    brand: Brand | None = None,
    crf: int = 18,
) -> RenderResult:
    brand = brand or load_brand(cut.brand)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    shots = [(get_shot(scene.shot)(scene), scene) for scene in cut.scenes]
    if profile.name.startswith("broll"):
        # A keyable element carries no endplate or captions (spec §6).
        shots = [(s, sc) for s, sc in shots if sc.shot not in {"endplate"}]

    duration = cut.duration
    total_frames = max(1, int(round(duration * profile.fps)))
    destination = encode.output_path(out_dir, cut.cut_id, profile)

    surface = _surface(profile)
    images: dict = {}

    process = subprocess.Popen(
        encode.encoder_command(profile, destination, crf),
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None

    png_dir = out_dir / f"{cut.cut_id}.{profile.name}.frames" if profile.png_sequence else None
    if png_dir is not None:
        png_dir.mkdir(parents=True, exist_ok=True)

    try:
        for frame_index in range(total_frames):
            t = frame_index / profile.fps
            with surface as canvas:
                render_frame(canvas, cut, corpus, profile, brand, t, frame_index, shots, images)
            image = surface.makeImageSnapshot()
            if png_dir is not None:
                image.save(str(png_dir / f"{frame_index:06d}.png"), skia.kPNG)
            process.stdin.write(_rgba_bytes(image, profile))
    except BrokenPipeError:
        pass
    finally:
        try:
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
        code = process.wait()

    if code != 0:
        raise RuntimeError(f"ffmpeg exited {code} while writing {destination}:\n{stderr.strip()}")

    srt = None
    if cut.captions.sidecar_srt and profile.public:
        entries = _caption_entries(cut)
        if entries:
            srt = encode.write_srt(entries, destination.with_suffix(".srt"))

    return RenderResult(
        profile=profile.name, path=destination, frames=total_frames, duration=duration, srt=srt
    )


def _rgba_bytes(image: skia.Image, profile: Profile) -> bytes:
    info = skia.ImageInfo.Make(
        profile.width, profile.height, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType
    )
    buffer = bytearray(profile.width * profile.height * 4)
    if not image.readPixels(info, buffer, profile.width * 4, 0, 0):
        raise RuntimeError("failed to read frame pixels from the Skia surface")
    return bytes(buffer)


def _caption_entries(cut: Cut) -> list[tuple[float, float, str]]:
    entries: list[tuple[float, float, str]] = []
    reading = [s for s in cut.scenes if s.shot in {"spotlight", "kinetic_typeset"}]
    if reading:
        first = min(s.t_in for s in reading)
        last = max(s.t_out for s in reading)
        entries.append((first, last, cut.source.verbatim))
    gloss = [s for s in cut.scenes if s.shot == "gloss_flip"]
    if gloss and cut.gloss.en:
        entries.append((min(s.t_in for s in gloss), max(s.t_out for s in gloss), cut.gloss.en))
    return entries
