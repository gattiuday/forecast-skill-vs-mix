"""Bootstrap resolution for the skill effect.

Rule four of this repository's receipts discipline: a measured effect is only
as good as the sample behind it. The skill effect is a weighted sum over SKUs,
so resampling SKUs with replacement gives an interval that reflects how much of
the effect is a property of which SKUs happened to be in the portfolio.

The interval is wide on purpose. Narrowing it would mean resampling weeks, which
assumes week to week independence that seasonal demand plainly violates.
"""

from __future__ import annotations

import numpy as np

from fsvm.config import DEFAULTS
from fsvm.decompose import _effects
from fsvm.panel import PopulationSplit


def skill_effect_interval(
    split: PopulationSplit,
    convention: str = "shapley",
    samples: int = DEFAULTS.bootstrap_samples,
    level: float = DEFAULTS.ci_level,
    seed: int = 20260419,
) -> dict[str, float]:
    """Percentile bootstrap interval for the skill effect, resampling SKUs.

    Returns the interval and a flag saying whether it contains zero. A skill
    effect whose interval contains zero is not a skill effect, and the CLI
    treats that case as an unfavourable answer rather than a failure.
    """
    rows = split.totals.loc[split.decomposable]
    a0 = rows["a0"].to_numpy(dtype=float)
    a1 = rows["a1"].to_numpy(dtype=float)
    f0 = rows["f0"].to_numpy(dtype=float)
    f1 = rows["f1"].to_numpy(dtype=float)
    n = a0.size

    rng = np.random.default_rng(seed)
    draws = np.empty(samples, dtype=float)
    for index in range(samples):
        pick = rng.integers(0, n, size=n)
        sa0, sa1 = a0[pick], a1[pick]
        if sa0.sum() <= 0 or sa1.sum() <= 0:
            draws[index] = np.nan
            continue
        w0 = sa0 / sa0.sum()
        w1 = sa1 / sa1.sum()
        e0 = np.abs(sa0 - f0[pick]) / sa0
        e1 = np.abs(sa1 - f1[pick]) / sa1
        draws[index] = _effects(convention, w0, w1, e0, e1)[0]

    valid = draws[np.isfinite(draws)]
    if valid.size < samples // 2:
        raise ValueError("more than half the bootstrap resamples were degenerate")
    tail = (1.0 - level) / 2.0
    low = float(np.quantile(valid, tail))
    high = float(np.quantile(valid, 1.0 - tail))
    return {
        "skill_effect_ci_low": low,
        "skill_effect_ci_high": high,
        "ci_level": float(level),
        "bootstrap_samples": int(valid.size),
        "contains_zero": bool(low <= 0.0 <= high),
    }
