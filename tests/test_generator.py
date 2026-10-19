"""Properties the fixture generator must hold for the experiments to mean anything."""

from __future__ import annotations

import pytest

from fsvm.generator import ARCHETYPE_MIX, SCENARIOS, generate_panel
from fsvm.panel import split_populations, to_period_totals, validate_panel


def test_the_generator_is_reproducible_for_a_fixed_seed():
    first = generate_panel(n_skus=60, seed=3)
    second = generate_panel(n_skus=60, seed=3)
    assert first.equals(second)


def test_a_different_seed_produces_a_different_panel():
    first = generate_panel(n_skus=60, seed=3)
    second = generate_panel(n_skus=60, seed=4)
    assert not first.equals(second)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_scenario_produces_a_panel_that_validates(scenario):
    assert len(validate_panel(generate_panel(n_skus=80, scenario=scenario))) > 0


def test_an_unknown_scenario_is_refused_by_name():
    with pytest.raises(ValueError, match="unknown scenario 'optimistic'"):
        generate_panel(scenario="optimistic")


def test_a_panel_shorter_than_two_seasons_is_refused():
    with pytest.raises(ValueError, match="at least 104 weeks"):
        generate_panel(weeks=80)


def test_an_impossible_churn_share_is_refused():
    with pytest.raises(ValueError, match="churn_share must be in"):
        generate_panel(churn_share=0.8)


def test_the_archetype_shares_sum_to_one():
    assert sum(ARCHETYPE_MIX.values()) == pytest.approx(1.0)


def test_every_sku_is_assigned_exactly_one_archetype():
    panel = generate_panel(n_skus=50)
    per_sku = panel.groupby("sku")["archetype"].nunique()
    assert (per_sku == 1).all()


def test_the_requested_number_of_skus_is_produced():
    assert generate_panel(n_skus=97)["sku"].nunique() == 97


def test_the_degenerate_scenarios_contain_no_churn():
    for scenario in ("pure_mix", "pure_skill"):
        panel = generate_panel(n_skus=80, scenario=scenario)
        weeks_per_sku = panel.groupby("sku")["week"].count()
        assert weeks_per_sku.nunique() == 1


def test_the_realistic_scenario_contains_launches_and_discontinuations():
    split = split_populations(
        to_period_totals(validate_panel(generate_panel(scenario="realistic")), 53)
    )
    assert len(split.entrants) > 0
    assert len(split.exits) > 0


def test_the_realistic_scenario_contains_skus_that_go_dormant_for_a_whole_period():
    split = split_populations(
        to_period_totals(validate_panel(generate_panel(scenario="realistic")), 53)
    )
    assert len(split.zero_actual) > 0


def test_demand_is_never_negative():
    assert (generate_panel(n_skus=80)["actual"] >= 0).all()


def test_forecasts_are_never_negative():
    assert (generate_panel(n_skus=80)["forecast"] >= 0).all()


def test_intermittent_skus_have_weeks_with_no_demand():
    panel = generate_panel(n_skus=120)
    intermittent = panel[panel["archetype"] == "intermittent"]
    assert (intermittent["actual"] == 0).any()


def test_the_pure_skill_scenario_holds_each_skus_period_volume_constant():
    panel = generate_panel(n_skus=80, scenario="pure_skill")
    totals = to_period_totals(validate_panel(panel), 53)
    ratio = totals["a1"] / totals["a0"]
    assert ratio.std() < 1e-3


def test_the_pure_mix_scenario_moves_volume_toward_the_forecastable_archetypes():
    panel = validate_panel(generate_panel(n_skus=160, scenario="pure_mix"))
    first = panel[panel["week"] < 53]
    second = panel[panel["week"] >= 53]
    share0 = first[first["archetype"] == "steady_seasonal"]["actual"].sum() / first["actual"].sum()
    share1 = (
        second[second["archetype"] == "steady_seasonal"]["actual"].sum() / second["actual"].sum()
    )
    assert share1 > share0
