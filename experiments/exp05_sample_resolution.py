"""How many SKUs does a portfolio need before a skill effect is distinguishable from none?

Question the README asks: the skill effect is a weighted sum over a sample of
SKUs. Rule four of this repository's receipts discipline says a measured
effect is only worth as much as the sample behind it. This measures the sample
size at which the bootstrap interval reliably excludes zero, so a planner can
tell whether their category is large enough to support the claim at all.

Reported as detection rate rather than as a single threshold, because the
answer depends on the effect size present in the data and this panel has one
particular effect size.
"""

from __future__ import annotations

import numpy as np
from _harness import emit, split_for, subset

from fsvm.decompose import decompose
from fsvm.resample import skill_effect_interval

SIZES = (20, 40, 80, 120, 160, 199)
TRIALS = 150
BOOTSTRAP = 400
TARGET_DETECTION = 0.80


def main() -> None:
    split = split_for("realistic")
    full_effect = decompose(split).skill_effect
    population = np.array(split.decomposable)
    rng = np.random.default_rng(90210)

    rows = []
    series = []
    for size in SIZES:
        detections = 0
        widths = []
        for trial in range(TRIALS):
            picked = rng.choice(population, size=min(size, population.size), replace=False)
            sample = subset(split, picked)
            interval = skill_effect_interval(
                sample, samples=BOOTSTRAP, seed=1000 + 7 * trial + size
            )
            widths.append(interval["skill_effect_ci_high"] - interval["skill_effect_ci_low"])
            if not interval["contains_zero"]:
                detections += 1
        rate = detections / TRIALS
        series.append(
            {
                "n_skus": size,
                "detection_rate": rate,
                "median_ci_width_points": float(np.median(widths)) * 100,
            }
        )
        rows.append((size, f"{rate:.0%}", f"{float(np.median(widths)) * 100:.2f}"))

    adequate = [row["n_skus"] for row in series if row["detection_rate"] >= TARGET_DETECTION]
    emit(
        "exp05_sample_resolution",
        {
            "question": "how many SKUs are needed before a skill effect is distinguishable",
            "full_population_skill_effect_points": full_effect * 100,
            "trials_per_size": TRIALS,
            "bootstrap_samples": BOOTSTRAP,
            "target_detection_rate": TARGET_DETECTION,
            "series": series,
            "smallest_adequate_n": min(adequate) if adequate else None,
            "detection_rate_at_20_skus": series[0]["detection_rate"],
            "note": (
                "a category smaller than the smallest adequate size cannot support a "
                "skill claim at this effect size, whatever the point estimate reads"
            ),
        },
        rows,
        ("n SKUs", "detects effect", "median CI width (pts)"),
    )


if __name__ == "__main__":
    main()
