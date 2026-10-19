"""Does the decomposition recover a planted answer?

Question the README asks: when the truth is known, does this tool find it?
Two scenarios have a closed form answer by construction. A tool that cannot
return zero where zero is the truth has no standing to report a number where
the truth is unknown.
"""

from __future__ import annotations

from _harness import emit, split_for

from fsvm.config import CONVENTIONS
from fsvm.decompose import decompose


def main() -> None:
    results = {}
    rows = []
    for scenario, planted_zero in (("pure_mix", "skill_effect"), ("pure_skill", "mix_effect")):
        split = split_for(scenario)
        for convention in CONVENTIONS:
            attribution = decompose(split, convention)
            residual = abs(getattr(attribution, planted_zero))
            results[f"{scenario}.{convention}"] = {
                "planted_zero_field": planted_zero,
                "measured_residual": residual,
                "restricted_delta": attribution.restricted_delta,
                "ratio_to_delta": residual / abs(attribution.restricted_delta),
            }
            rows.append(
                (
                    scenario,
                    convention,
                    planted_zero.replace("_effect", ""),
                    f"{residual:.3e}",
                    f"{residual / abs(attribution.restricted_delta):.2e}",
                )
            )

    worst = max(entry["measured_residual"] for entry in results.values())
    emit(
        "exp01_recovery",
        {
            "question": "does the decomposition return zero where zero is the planted truth",
            "per_case": results,
            "worst_residual": worst,
            "worst_residual_ratio": max(entry["ratio_to_delta"] for entry in results.values()),
            "note": (
                "the residual is fixture rounding, not method error: demand is stored to "
                "three decimals so it round trips through CSV byte for byte"
            ),
        },
        rows,
        ("scenario", "convention", "planted zero", "residual", "vs delta"),
    )


if __name__ == "__main__":
    main()
