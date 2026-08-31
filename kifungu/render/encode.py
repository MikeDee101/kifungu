"""FFmpeg assembly (spec §6).

Two hard rules live here:

* every H.264 output is ``-pix_fmt yuv420p``, without which the file will not
  play in browsers, WhatsApp or PowerPoint;
* encoding is bit-exact and carries no metadata, so two renders of one Cut
  produce identical file hashes (§13 determinism).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from kifungu.platform import find_ffmpeg, find_ffprobe
from kifungu.render.profiles import Profile

# Strips encoder version strings and timestamps, which would otherwise differ
# between two otherwise identical renders. ffmpeg is position-sensitive: these
# must go on the correct side of -i or it refuses to start.
BITEXACT_IN = ["-fflags", "+bitexact"]
BITEXACT_OUT = ["-flags:v", "+bitexact", "-map_metadata", "-1"]


def output_path(out_dir: Path, cut_id: str, profile: Profile) -> Path:
    return Path(out_dir) / f"{cut_id}.{profile.name.replace('@', '_')}.{profile.container}"


def _codec_args(profile: Profile, crf: int) -> list[str]:
    if profile.codec == "prores_ks":
        return [
            *BITEXACT_OUT,
            "-c:v", "prores_ks",
            "-profile:v", "4444",       # the only ProRes profile carrying alpha
            "-pix_fmt", profile.pix_fmt,
            "-alpha_bits", "16",
            "-vendor", "apl0",
        ]
    return [
        *BITEXACT_OUT,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(crf),
        "-pix_fmt", profile.pix_fmt,   # yuv420p — non-negotiable for playback
        "-movflags", "+faststart",
    ]


def encoder_command(profile: Profile, destination: Path, crf: int = 18) -> list[str]:
    """ffmpeg reading raw RGBA frames on stdin.

    Note the absence of ``-nostdin``: stdin *is* the video input here, and
    passing that flag makes ffmpeg ignore the pipe we are feeding.
    """
    return [
        find_ffmpeg(),
        "-hide_banner", "-loglevel", "error", "-y",
        *BITEXACT_IN,
        "-f", "rawvideo",
        "-pixel_format", "rgba",
        "-video_size", f"{profile.width}x{profile.height}",
        "-framerate", str(profile.fps),
        "-i", "-",
        *_codec_args(profile, crf),
        str(destination),
    ]


def encode_from_pngs(profile: Profile, pattern: str, destination: Path, crf: int = 18) -> None:
    command = [
        find_ffmpeg(),
        "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        *BITEXACT_IN,
        "-framerate", str(profile.fps),
        "-i", pattern,
        *_codec_args(profile, crf),
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr.strip()}")


def probe_pix_fmt(path: Path) -> str:
    """Read back the pixel format — used by the playback-compatibility test."""
    ffprobe = find_ffprobe()
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def _timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(entries: list[tuple[float, float, str]], destination: Path) -> Path:
    """Sidecar captions. Entries are (start, end, text) in seconds."""
    lines: list[str] = []
    for index, (start, end, text) in enumerate(entries, start=1):
        lines.append(str(index))
        lines.append(f"{_timestamp(start)} --> {_timestamp(end)}")
        lines.append(text.replace("\n", " ").strip())
        lines.append("")
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination
