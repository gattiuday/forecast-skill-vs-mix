"""A seasonal naive referee, because a skill effect with no baseline is not a skill claim.

A decomposition can report that per SKU errors fell and still be describing a
period that was simply easier to forecast. The only defence is a third forecast
that nobody tuned: last season's actual, carried forward. Where the model fails
to beat that, the word "model" is doing no work.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fsvm.errors import AttributionError
from fsvm.metrics import mase

DEFAULT_SEASON_WEEKS = 52


def seasonal_naive(series: np.ndarray, season: int = DEFAULT_SEASON_WEEKS) -> np.ndarray:
    """Carry the value from `season` periods earlier forward.

    The first `season` entries have no predecessor and are returned as NaN
    rather than back filled. Back filling would invent a referee that saw the
    future, which is exactly the error this module exists to catch.
    """
    values = np.asarray(series, dtype=float)
    if season < 1:
        raise AttributionError(f"season must be at least 1, got {season}")
    out = np.full(values.shape, np.nan, dtype=float)
    if values.size > season:
        out[season:] = values[:-season]
    return out


def beat_rate(
    frame: pd.DataFrame, split_week: int, season: int = DEFAULT_SEASON_WEEKS
) -> dict[str, float]:
    """How often the forecast beats the seasonal naive referee in period one.

    Returns both an unweighted rate over SKUs and a volume weighted rate,
    because they answer different questions and routinely disagree. A model can
    beat the referee on most SKUs and lose on most of the volume, which is the
    case a portfolio metric hides most effectively.
    """
    results: list[tuple[str, float, float]] = []
    undefined = 0
    for sku, rows in frame.sort_values("week").groupby("sku", sort=True):
        actual = rows["actual"].to_numpy(dtype=float)
        forecast = rows["forecast"].to_numpy(dtype=float)
        naive = seasonal_naive(actual, season)
        evaluate = (rows["week"].to_numpy() >= split_week) & np.isfinite(naive)
        if evaluate.sum() < 4:
            undefined += 1
            continue
        try:
            score = mase(actual[evaluate], forecast[evaluate], naive[evaluate])
        except ValueError:
            undefined += 1
            continue
        results.append((str(sku), score, float(actual[evaluate].sum())))

    if not results:
        raise AttributionError(
            "no SKU has enough history after the split week to score against a "
            f"seasonal naive referee with season={season}"
        )
    scores = np.array([row[1] for row in results])
    volumes = np.array([row[2] for row in results])
    beat = scores < 1.0
    weighted = float(volumes[beat].sum() / volumes.sum()) if volumes.sum() > 0 else 0.0
    return {
        "n_scored": len(results),
        "n_undefined": int(undefined),
        "beat_rate_unweighted": float(beat.mean()),
        "beat_rate_volume_weighted": weighted,
        "median_mase": float(np.median(scores)),
        "season_weeks": int(season),
    }
