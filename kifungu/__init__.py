"""Kifungu — turns institutional documents into broadcast-quality motion graphics."""

from __future__ import annotations


def _detect_version() -> str:
    # Written by hatch-vcs at build time from the git tag. This is the value that
    # ends up in every Cut and manifest, so stale-Cut detection (spec §8.5) only
    # works if it tracks the release the operator is actually running.
    try:
        from kifungu._version import __version__ as v

        return str(v)
    except ImportError:
        pass
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("kifungu")
        except PackageNotFoundError:
            pass
    except ImportError:
        pass
    return "0.0.0+dev"


__version__ = _detect_version()
__all__ = ["__version__"]
