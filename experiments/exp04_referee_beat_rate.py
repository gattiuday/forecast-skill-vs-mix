"""Does the forecast beat a referee nobody tuned, and does the answer depend on how you count?

Question the README asks: a skill effect says errors fell. It does not say the
model earned that. A seasonal naive carry forward is the cheapest possible
competitor, and the unweighted and volume weighted beat rates against it
routinely point in opposite directions.
"""

from __future__ import annotations

from _harness import SPLIT_WEEK, emit, panel

from fsvm.baseline import beat_rate

SEASONS = (26, 52)


def main() -> None:
    frame = panel("realistic")
    rows = []
    per_season = {}
    for season in SEASONS:
        scores = beat_rate(frame, SPLIT_WEEK, season=season)
        per_season[str(season)] = scores
        rows.append(
            (
                season,
                scores["n_scored"],
                scores["n_undefined"],
                f"{scores['beat_rate_unweighted']:.1%}",
                f"{scores['beat_rate_volume_weighted']:.1%}",
                f"{scores['median_mase']:.2f}",
            )
        )

    headline = per_season["52"]
    emit(
        "exp04_referee_beat_rate",
        {
            "question": "does the forecast beat a seasonal naive referee, and on what count",
            "per_season": per_season,
            "beat_rate_unweighted_pct": headline["beat_rate_unweighted"] * 100,
            "beat_rate_weighted_pct": headline["beat_rate_volume_weighted"] * 100,
            "loses_unweighted_pct": (1.0 - headline["beat_rate_unweighted"]) * 100,
            "counting_gap_points": (
                headline["beat_rate_volume_weighted"] - headline["beat_rate_unweighted"]
            )
            * 100,
            "note": (
                "the fixture's forecast is constructed, so the absolute level of these "
                "rates is a property of the generator. The gap between the two ways of "
                "counting is the finding, not the level."
            ),
        },
        rows,
        ("season", "scored", "undefined", "beats (SKUs)", "beats (volume)", "median MASE"),
    )


if __name__ == "__main__":
    main()
