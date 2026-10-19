"""How much of the skill versus mix split is a modelling choice rather than a measurement?

Question the README asks: if four standard conventions disagree, by how much?
A tool that reports one number is not more accurate than one that reports four,
it is just quieter about the arbitrary step.
"""

from __future__ import annotations

from _harness import emit, split_for

from fsvm.decompose import convention_spread, decompose_all_conventions


def main() -> None:
    split = split_for("realistic")
    results = decompose_all_conventions(split)
    spread = convention_spread(results)
    any_result = next(iter(results.values()))

    rows = [
        (
            name,
            f"{result.skill_effect * 100:+.2f}",
            f"{result.mix_effect * 100:+.2f}",
            f"{result.interaction_effect * 100:+.2f}",
            f"{abs(result.skill_effect / any_result.total_delta):.0%}",
        )
        for name, result in results.items()
    ]

    skill_shares = [abs(r.skill_effect / any_result.total_delta) for r in results.values()]
    emit(
        "exp02_convention_spread",
        {
            "question": "how far apart do four standard conventions put the skill mix split",
            "total_delta": any_result.total_delta,
            "wmape_period0": any_result.wmape_period0,
            "wmape_period1": any_result.wmape_period1,
            "per_convention": {name: result.as_dict() for name, result in results.items()},
            "spread": spread,
            "skill_share_min": min(skill_shares),
            "skill_share_max": max(skill_shares),
            "skill_share_spread_points": (max(skill_shares) - min(skill_shares)) * 100,
        },
        rows,
        ("convention", "skill pts", "mix pts", "interaction", "skill share"),
    )


if __name__ == "__main__":
    main()
