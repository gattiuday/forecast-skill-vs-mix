"""Turn an attribution into a verdict and a console table.

The verdict is deliberately separate from the arithmetic. `decompose` says what
the numbers are; this module says what they mean under a stated policy, and the
policy lives in `config` where it can be argued with. Mixing the two is how a
tool ends up with a threshold nobody can find.
"""

from __future__ import annotations

from dataclasses import dataclass

from fsvm.config import DEFAULTS, Thresholds
from fsvm.decompose import Attribution

ATTRIBUTED = "attributed"
NOT_ATTRIBUTED = "not_attributed"


@dataclass(frozen=True)
class Verdict:
    """The answer, and every reason it came out that way.

    `reasons` is always populated, including on a pass, so that a green result
    in a log is as auditable as a red one.
    """

    status: str
    reasons: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        return 0 if self.status == ATTRIBUTED else 1


def judge(
    attribution: Attribution,
    interval: dict[str, float],
    thresholds: Thresholds = DEFAULTS,
) -> Verdict:
    """Decide whether an accuracy improvement can be credited to forecasting skill."""
    reasons: list[str] = []

    if attribution.total_delta >= 0:
        reasons.append(
            f"portfolio WMAPE did not improve: it moved by {attribution.total_delta * 100:+.2f} "
            "points"
        )
    if attribution.skill_effect >= 0:
        reasons.append(
            f"the skill effect is {attribution.skill_effect * 100:+.2f} points, so per SKU "
            "errors got worse even if the portfolio number got better"
        )
    if interval["contains_zero"]:
        reasons.append(
            f"the {interval['ci_level']:.0%} bootstrap interval on the skill effect "
            f"[{interval['skill_effect_ci_low'] * 100:+.2f}, "
            f"{interval['skill_effect_ci_high'] * 100:+.2f}] contains zero, so the sample of "
            "SKUs cannot distinguish the effect from none"
        )
    if attribution.unattributable_volume_share > thresholds.max_churn_share:
        reasons.append(
            f"{attribution.unattributable_volume_share:.1%} of volume sits in SKUs that entered, "
            f"exited or went dormant, above the limit of {thresholds.max_churn_share:.0%}; no "
            "split of the remainder is worth reporting"
        )

    if reasons:
        return Verdict(NOT_ATTRIBUTED, tuple(reasons))

    share = abs(attribution.skill_effect / attribution.total_delta)
    return Verdict(
        ATTRIBUTED,
        (
            f"skill accounts for {share:.0%} of a "
            f"{abs(attribution.total_delta) * 100:.2f} point improvement",
            "the bootstrap interval on the skill effect excludes zero",
            f"unattributable volume is {attribution.unattributable_volume_share:.1%}, "
            f"within the limit of {thresholds.max_churn_share:.0%}",
        ),
    )


def _points(value: float) -> str:
    return f"{value * 100:+.2f}"


def render_table(results: dict[str, Attribution], spread: dict[str, float]) -> str:
    """A fixed width table of every convention, so the disagreement is visible at once."""
    any_result = next(iter(results.values()))
    lines = [
        f"Portfolio WMAPE  period 0: {any_result.wmape_period0:.4f}   "
        f"period 1: {any_result.wmape_period1:.4f}   "
        f"change: {_points(any_result.total_delta)} points",
        "",
        f"{'convention':<12} {'skill':>9} {'mix':>9} {'interaction':>12} {'sums to':>9}",
        "-" * 54,
    ]
    for name, result in results.items():
        total = result.skill_effect + result.mix_effect + result.interaction_effect
        lines.append(
            f"{name:<12} {_points(result.skill_effect):>9} {_points(result.mix_effect):>9} "
            f"{_points(result.interaction_effect):>12} {_points(total):>9}"
        )
    lines += [
        "-" * 54,
        f"spread across conventions: skill {spread['skill_effect_spread'] * 100:.2f} points, "
        f"mix {spread['mix_effect_spread'] * 100:.2f} points",
        "",
        f"Unattributable change: {_points(any_result.unattributable_delta)} points "
        f"({any_result.unattributable_volume_share:.1%} of volume)",
        f"  entrants {any_result.n_entrants}, exits {any_result.n_exits}, "
        f"zero demand in a period {any_result.n_zero_actual}, "
        f"decomposable {any_result.n_decomposable}",
    ]
    return "\n".join(lines)
