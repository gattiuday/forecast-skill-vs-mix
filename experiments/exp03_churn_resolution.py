"""At what level of catalogue churn does an attribution stop meaning anything?

Question the README asks: entrants and exits have no counterfactual, so their
contribution to a WMAPE change cannot be split at all. How big does that
unattributable share get, and at what point does it dominate the answer?
"""

from __future__ import annotations

from _harness import emit, split_for

from fsvm.decompose import decompose

CHURN_LEVELS = (0.0, 0.05, 0.12, 0.20, 0.30, 0.40, 0.48)


def main() -> None:
    rows = []
    series = []
    for churn in CHURN_LEVELS:
        split = split_for("realistic", churn_share=churn)
        result = decompose(split)
        unattributable_share = abs(result.unattributable_delta / result.total_delta)
        series.append(
            {
                "churn_share_requested": churn,
                "n_decomposable": result.n_decomposable,
                "n_entrants": result.n_entrants,
                "n_exits": result.n_exits,
                "n_zero_actual": result.n_zero_actual,
                "total_delta": result.total_delta,
                "unattributable_delta": result.unattributable_delta,
                "unattributable_share_of_change": unattributable_share,
                "unattributable_volume_share": result.unattributable_volume_share,
            }
        )
        rows.append(
            (
                f"{churn:.0%}",
                result.n_decomposable,
                result.n_entrants + result.n_exits + result.n_zero_actual,
                f"{result.total_delta * 100:+.2f}",
                f"{result.unattributable_delta * 100:+.2f}",
                f"{unattributable_share:.0%}",
            )
        )

    worst = max(series, key=lambda row: row["unattributable_share_of_change"])
    emit(
        "exp03_churn_resolution",
        {
            "question": "how much of a WMAPE change becomes unattributable as churn rises",
            "series": series,
            "max_unattributable_share": worst["unattributable_share_of_change"],
            "max_unattributable_share_at_churn": worst["churn_share_requested"],
            "note": (
                "the zero churn case still has an unattributable share, because SKUs that "
                "go dormant for a whole period are present in both periods and still have "
                "no defined percentage error"
            ),
        },
        rows,
        ("churn", "decomposable", "excluded", "total pts", "unattr pts", "share"),
    )


if __name__ == "__main__":
    main()
