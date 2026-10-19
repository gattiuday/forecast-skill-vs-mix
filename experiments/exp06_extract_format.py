"""How much does the referee's answer depend on whether the extract includes zero sales weeks?

Question the README asks: an ERP sales extract usually omits weeks with no
sales. A seasonal referee that shifts by row position therefore reaches back a
different number of weeks for every SKU. This measures what that cost, by
running the superseded positional implementation beside the current one.

The positional function below is kept here, in an experiment, rather than in
the library. It is the bug, preserved so its size can be quoted.
"""

from __future__ import annotations

import numpy as np
from _harness import SPLIT_WEEK, emit, panel

from fsvm.baseline import MIN_SCORED_WEEKS, beat_rate
from fsvm.metrics import mase

SEASON = 52


def positional_beat_rate(frame, split_week: int, season: int = SEASON) -> dict[str, float]:
    """The superseded implementation: shift by `season` rows, not `season` weeks."""
    scores, volumes = [], []
    for _, rows in frame.sort_values("week").groupby("sku", sort=True):
        actual = rows["actual"].to_numpy(dtype=float)
        forecast = rows["forecast"].to_numpy(dtype=float)
        naive = np.full(actual.shape, np.nan)
        if actual.size > season:
            naive[season:] = actual[:-season]
        pick = (rows["week"].to_numpy() >= split_week) & np.isfinite(naive)
        if pick.sum() < MIN_SCORED_WEEKS:
            continue
        try:
            scores.append(mase(actual[pick], forecast[pick], naive[pick]))
        except ValueError:
            continue
        volumes.append(float(actual[pick].sum()))
    scores_array, volume_array = np.array(scores), np.array(volumes)
    beat = scores_array < 1.0
    return {
        "n_scored": len(scores),
        "beat_rate_unweighted": float(beat.mean()),
        "beat_rate_volume_weighted": float(volume_array[beat].sum() / volume_array.sum()),
        "median_mase": float(np.median(scores_array)),
    }


def main() -> None:
    dense = panel("realistic")
    sparse = dense[dense["actual"] > 0].reset_index(drop=True)

    measurements = {
        "positional_dense": positional_beat_rate(dense, SPLIT_WEEK),
        "positional_sparse": positional_beat_rate(sparse, SPLIT_WEEK),
        "week_aligned_dense": beat_rate(dense, SPLIT_WEEK, SEASON),
        "week_aligned_sparse": beat_rate(sparse, SPLIT_WEEK, SEASON),
    }
    rows = [
        (
            name.replace("_", " "),
            value["n_scored"],
            f"{value['beat_rate_unweighted']:.1%}",
            f"{value['beat_rate_volume_weighted']:.1%}",
            f"{value['median_mase']:.2f}",
        )
        for name, value in measurements.items()
    ]

    positional_gap = abs(
        measurements["positional_dense"]["beat_rate_unweighted"]
        - measurements["positional_sparse"]["beat_rate_unweighted"]
    )
    aligned_gap = abs(
        measurements["week_aligned_dense"]["beat_rate_unweighted"]
        - measurements["week_aligned_sparse"]["beat_rate_unweighted"]
    )
    emit(
        "exp06_extract_format",
        {
            "question": (
                "how much does the referee depend on the extract including zero sales weeks"
            ),
            "measurements": measurements,
            "positional_gap_points": positional_gap * 100,
            "week_aligned_gap_points": aligned_gap * 100,
            "artifact_removed_points": (positional_gap - aligned_gap) * 100,
            "rows_dropped": int(len(dense) - len(sparse)),
            "note": (
                "the residual gap under week alignment is genuine information loss: a "
                "sparse extract has fewer weeks carrying a recorded forecast to grade, "
                "so fewer SKUs clear the minimum scored week count"
            ),
        },
        rows,
        ("variant", "scored", "beats (SKUs)", "beats (volume)", "median MASE"),
    )


if __name__ == "__main__":
    main()
