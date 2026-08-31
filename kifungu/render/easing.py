"""Easing functions (spec §5).

The only permitted way to interpolate. No linear motion except deliberate
machine-like sweeps, for which `linear` is provided explicitly so that choosing
it is visible in the Cut rather than accidental.

Every function maps t in [0, 1] to an eased value, with f(0) == 0 and f(1) == 1.
`out_back` and `spring` deliberately overshoot in between.
"""

from __future__ import annotations

import math
from collections.abc import Callable

Ease = Callable[[float], float]


def linear(t: float) -> float:
    return t


def out_quint(t: float) -> float:
    return 1.0 - pow(1.0 - t, 5)


def in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - pow(-2.0 * t + 2.0, 3) / 2.0


def out_back(t: float, overshoot: float = 1.70158) -> float:
    c3 = overshoot + 1.0
    return 1.0 + c3 * pow(t - 1.0, 3) + overshoot * pow(t - 1.0, 2)


def spring(t: float, damping: float = 8.0, frequency: float = 3.2) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 1.0 - math.exp(-damping * t) * math.cos(frequency * math.pi * t)


def out_cubic(t: float) -> float:
    return 1.0 - pow(1.0 - t, 3)


def in_out_quad(t: float) -> float:
    return 2.0 * t * t if t < 0.5 else 1.0 - pow(-2.0 * t + 2.0, 2) / 2.0


EASINGS: dict[str, Ease] = {
    "linear": linear,
    "out_quint": out_quint,
    "out_cubic": out_cubic,
    "in_out_cubic": in_out_cubic,
    "in_out_quad": in_out_quad,
    "out_back": out_back,
    "spring": spring,
}


def get(name: str) -> Ease:
    try:
        return EASINGS[name]
    except KeyError:
        raise KeyError(f"unknown easing {name!r}; available: {sorted(EASINGS)}") from None


def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def ramp(t: float, start: float, duration: float, ease: str = "out_quint") -> float:
    """Progress of a sub-animation starting at `start` and lasting `duration`."""
    if duration <= 0.0:
        return 1.0 if t >= start else 0.0
    return get(ease)(clamp01((t - start) / duration))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
