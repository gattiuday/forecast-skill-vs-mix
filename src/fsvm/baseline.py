"""A seasonal naive referee, because a skill effect with no baseline is not a skill claim.

A decomposition can report that per SKU errors fell and still be describing a
period that was simply easier to forecast. The only defence is a third forecast
that nobody tuned: last season's actual, carried forward. Where the model fails
to beat that, the word "model" is doing no work.

The referee is aligned on week numbers, not on row positions. That distinction
is not pedantic. An ERP sales extract usually omits weeks with no sales, so the
rows for a slow moving SKU are not contiguous, and a positional shift of 52 rows
reaches back an arbitrary number of weeks. See ADR-004 and the war story in the
README: on this repository's own fixture, the positional version moved the
unweighted beat rate by 17.7 points.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fsvm.errors import AttributionError
from fsvm.metrics import mase

DEFAULT_SEASON_WEEKS = 52
MIN_SCORED_WEEKS = 4


def seasonal_naive(weeks, values, season: int = DEFAULT_SEASON_WEEKS) -> np.ndarray:
    """Return, for each week, the actual from `season` weeks earlier.

    Weeks with no predecessor in the series are NaN rather than back filled.
    Back filling would invent a referee that saw the future, which is exactly
    the error this module exists to catch.
    """
    if season < 1:
        raise AttributionError(f"season must be at least 1, got {season}")
    week_array = np.asarray(weeks, dtype=int)
    value_array = np.asarray(values, dtype=float)
    if week_array.shape != value_array.shape:
        raise AttributionError(
            f"weeks and values differ in length: {week_array.size} and {value_array.size}"
        )
    lookup = dict(zip(week_array.tolist(), value_array.tolist(), strict=True))
    return np.array([lookup.get(int(week) - season, np.nan) for week in week_array], dtype=float)


def densify(frame: pd.DataFrame, fill_value: float = 0.0) -> pd.DataFrame:
    """Insert a zero demand row for every week a SKU is missing inside its own span.

    A missing week in a sales extract means no sales, not no information. That
    reading is an assumption about the upstream system rather than a fact about
    the data, so it is applied in one named function and recorded in ADR-004,
    not scattered through the scoring code.

    Only weeks inside each SKU's own first to last observed span are filled.
    Padding a launch backwards to the start of the panel would invent history.
    The inserted rows carry a `filled` flag so scoring can refuse to grade a
    forecast that was never actually made.
    """
    pieces = []
    for sku, rows in frame.groupby("sku", sort=True):
        span = np.arange(int(rows["week"].min()), int(rows["week"].max()) + 1)
        reindexed = (
            rows.set_index("week").reindex(span).rename_axis("week").reset_index().assign(sku=sku)
        )
        reindexed["filled"] = reindexed["actual"].isna()
        reindexed["actual"] = reindexed["actual"].fillna(fill_value)
        pieces.append(reindexed)
    return pd.concat(pieces, ignore_index=True)


def beat_rate(
    frame: pd.DataFrame, split_week: int, season: int = DEFAULT_SEASON_WEEKS
) -> dict[str, float]:
    """How often the forecast beats the seasonal naive referee in period one.

    Returns both an unweighted rate over SKUs and a volume weighted rate,
    because they answer different questions and routinely disagree. A model can
    lose to the referee on most SKUs and still win on most of the volume, which
    is the case a portfolio metric hides most effectively.

    Weeks inserted by `densify` inform the referee but are never scored, so a
    forecast is only graded where one was actually recorded.
    """
    dense = densify(frame)
    results: list[tuple[str, float, float]] = []
    undefined = 0

    for sku, rows in dense.sort_values("week").groupby("sku", sort=True):
        weeks = rows["week"].to_numpy(dtype=int)
        actual = rows["actual"].to_numpy(dtype=float)
        forecast = rows["forecast"].to_numpy(dtype=float)
        naive = seasonal_naive(weeks, actual, season)
        scorable = (
            (weeks >= split_week)
            & np.isfinite(naive)
            & np.isfinite(forecast)
            & ~rows["filled"].to_numpy(dtype=bool)
        )
        if scorable.sum() < MIN_SCORED_WEEKS:
            undefined += 1
            continue
        try:
            score = mase(actual[scorable], forecast[scorable], naive[scorable])
        except ValueError:
            undefined += 1
            continue
        results.append((str(sku), score, float(actual[scorable].sum())))

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
