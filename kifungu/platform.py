"""Windows-specific runtime fixes, applied once at process start.

Windows is the release target, so these are load-bearing rather than defensive.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def configure_stdio() -> None:
    """Force UTF-8 on stdout/stderr.

    A default Windows console is cp1252, which raises UnicodeEncodeError on the
    elision character '…' (spec §8.2) and on any Kiswahili gloss. Printing a
    citation must never be able to crash a render.
    """
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def bundle_dir() -> Path | None:
    """Directory of the frozen bundle, or None when running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return None


def find_ffmpeg() -> str:
    """Resolve ffmpeg: bundled binary first, then PATH.

    Releases ship ffmpeg in `_bin/` so an operator needs no separate install.
    """
    bundle = bundle_dir()
    if bundle is not None:
        candidate = bundle / "_bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if candidate.exists():
            return str(candidate)

    found = shutil.which("ffmpeg")
    if found:
        return found

    raise FileNotFoundError(
        "ffmpeg was not found.\n"
        "  Windows release builds bundle it in _bin/ — if that folder is missing, "
        "re-download the release zip.\n"
        "  Running from source? Install ffmpeg and put it on PATH: "
        "https://ffmpeg.org/download.html"
    )


def find_ffprobe() -> str:
    """Resolve ffprobe: beside the resolved ffmpeg first, then PATH.

    Derived by string-replacing 'ffmpeg' in the ffmpeg path would corrupt
    directory names like 'ffmpeg-8.1-full_build', so look for the sibling file
    by name instead.
    """
    exe = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    sibling = Path(find_ffmpeg()).parent / exe
    if sibling.exists():
        return str(sibling)

    found = shutil.which("ffprobe")
    if found:
        return found

    raise FileNotFoundError("ffprobe was not found next to ffmpeg or on PATH.")
