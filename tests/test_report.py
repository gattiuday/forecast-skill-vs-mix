"""The verdict policy, kept separate from the arithmetic so it can be argued with."""

from __future__ import annotations

from fsvm.config import Thresholds
from fsvm.decompose import convention_spread, decompose, decompose_all_conventions
from fsvm.report import ATTRIBUTED, NOT_ATTRIBUTED, judge, render_table
from fsvm.resample import skill_effect_interval

CLEAN_INTERVAL = {
    "skill_effect_ci_low": -0.02,
    "skill_effect_ci_high": -0.005,
    "ci_level": 0.90,
    "bootstrap_samples": 2000,
    "contains_zero": False,
}
ZERO_SPANNING_INTERVAL = {**CLEAN_INTERVAL, "skill_effect_ci_high": 0.004, "contains_zero": True}


def _with(attribution, **changes):
    return type(attribution)(**{**attribution.as_dict(), **changes})


def test_a_genuine_improvement_with_a_clean_interval_is_attributed(realistic_split):
    verdict = judge(decompose(realistic_split), CLEAN_INTERVAL)
    assert verdict.status == ATTRIBUTED
    assert verdict.exit_code == 0


def test_an_attributed_verdict_still_states_its_reasons(realistic_split):
    verdict = judge(decompose(realistic_split), CLEAN_INTERVAL)
    assert len(verdict.reasons) == 3


def test_an_interval_containing_zero_withholds_attribution(realistic_split):
    verdict = judge(decompose(realistic_split), ZERO_SPANNING_INTERVAL)
    assert verdict.status == NOT_ATTRIBUTED
    assert verdict.exit_code == 1
    assert any("contains zero" in reason for reason in verdict.reasons)


def test_a_worsening_portfolio_metric_withholds_attribution(realistic_split):
    verdict = judge(_with(decompose(realistic_split), total_delta=0.015), CLEAN_INTERVAL)
    assert verdict.status == NOT_ATTRIBUTED
    assert any("did not improve" in reason for reason in verdict.reasons)


def test_a_positive_skill_effect_withholds_attribution_even_when_the_portfolio_improved(
    realistic_split,
):
    """The case the whole repository exists for: the headline number got better
    while per SKU accuracy got worse."""
    verdict = judge(_with(decompose(realistic_split), skill_effect=0.004), CLEAN_INTERVAL)
    assert verdict.status == NOT_ATTRIBUTED
    assert any("per SKU errors got worse" in reason for reason in verdict.reasons)


def test_excessive_churn_withholds_attribution(realistic_split):
    verdict = judge(
        _with(decompose(realistic_split), unattributable_volume_share=0.60), CLEAN_INTERVAL
    )
    assert verdict.status == NOT_ATTRIBUTED
    assert any("entered, exited or went dormant" in reason for reason in verdict.reasons)


def test_the_churn_limit_is_configurable_rather_than_hard_coded(realistic_split):
    attribution = _with(decompose(realistic_split), unattributable_volume_share=0.40)
    strict = judge(attribution, CLEAN_INTERVAL, Thresholds(max_churn_share=0.35))
    lenient = judge(attribution, CLEAN_INTERVAL, Thresholds(max_churn_share=0.50))
    assert strict.status == NOT_ATTRIBUTED
    assert lenient.status == ATTRIBUTED


def test_several_failures_are_all_reported_rather_than_short_circuiting(realistic_split):
    attribution = _with(
        decompose(realistic_split),
        total_delta=0.01,
        skill_effect=0.01,
        unattributable_volume_share=0.9,
    )
    verdict = judge(attribution, ZERO_SPANNING_INTERVAL)
    assert len(verdict.reasons) == 4


def test_the_table_shows_every_convention(realistic_split):
    results = decompose_all_conventions(realistic_split)
    table = render_table(results, convention_spread(results))
    for name in results:
        assert name in table


def test_the_table_shows_that_each_convention_sums_to_the_same_total(realistic_split):
    results = decompose_all_conventions(realistic_split)
    table = render_table(results, convention_spread(results))
    sums = [line.split()[-1] for line in table.splitlines() if line.startswith(tuple(results))]
    assert len(set(sums)) == 1


def test_the_table_names_the_unattributable_populations(realistic_split):
    results = decompose_all_conventions(realistic_split)
    table = render_table(results, convention_spread(results))
    assert "entrants" in table
    assert "zero demand in a period" in table


def test_the_table_reports_the_spread_between_conventions(realistic_split):
    results = decompose_all_conventions(realistic_split)
    table = render_table(results, convention_spread(results))
    assert "spread across conventions" in table


def test_the_real_interval_and_the_real_attribution_agree_with_the_verdict(realistic_split):
    """The fixture is built to be attributable, so the end to end path must say so.

    An earlier version of this test asserted only that the status was one of the
    two possible statuses, which cannot fail and was pure test count padding.
    An audit caught it.
    """
    attribution = decompose(realistic_split)
    interval = skill_effect_interval(realistic_split, samples=400)
    verdict = judge(attribution, interval)
    assert verdict.status == ATTRIBUTED
    assert verdict.exit_code == 0
    assert any("skill accounts for" in reason for reason in verdict.reasons)


def test_no_report_line_contains_an_em_dash(realistic_split):
    results = decompose_all_conventions(realistic_split)
    table = render_table(results, convention_spread(results))
    verdict = judge(decompose(realistic_split), ZERO_SPANNING_INTERVAL)
    assert "—" not in table
    assert all("—" not in reason for reason in verdict.reasons)


def test_the_generated_table_block_matches_the_console_table(realistic_split):
    """The README's convention table is generated by `render_table_rows` and the
    console prints it via `render_table`. They share a column layout, so a change
    to one that is not made to the other would publish two different tables of the
    same numbers."""
    from fsvm.report import render_table_rows

    results = decompose_all_conventions(realistic_split)
    block = render_table_rows({name: r.as_dict() for name, r in results.items()})
    console = render_table(results, convention_spread(results))
    for line in block.strip().split("\n"):
        assert line in console


def test_the_generated_block_lists_the_conventions_in_their_declared_order(realistic_split):
    from fsvm.config import CONVENTIONS
    from fsvm.report import render_table_rows

    results = decompose_all_conventions(realistic_split)
    block = render_table_rows({name: r.as_dict() for name, r in results.items()})
    names = [line.split()[0] for line in block.strip().split("\n")[2:]]
    assert names == list(CONVENTIONS)


def test_the_generated_block_rows_each_sum_to_the_same_total(realistic_split):
    from fsvm.report import render_table_rows

    results = decompose_all_conventions(realistic_split)
    block = render_table_rows({name: r.as_dict() for name, r in results.items()})
    totals = {line.split()[-1] for line in block.strip().split("\n")[2:]}
    assert len(totals) == 1
