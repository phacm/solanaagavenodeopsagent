"""Model-quality gate statistics (plan §8.1, P-23): Wilson score interval; a gate passes
on the LOWER confidence bound, never on the point estimate."""
from __future__ import annotations

import math
from statistics import NormalDist


def wilson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def gate(k: int, n: int, target_lcb: float, confidence: float = 0.95) -> dict:
    lo, hi = wilson(k, n, confidence)
    return {"k": k, "n": n, "point": k / n if n else None, "lcb": lo, "ucb": hi, "target": target_lcb, "pass": lo >= target_lcb}
