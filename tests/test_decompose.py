"""The decomposition's exactness, its recovery of planted ground truth, and its refusals."""

from __future__ import annotations

import pytest

from fsvm.config import CONVENTIONS
from fsvm.decompose import (
    convention_spread,
    decompose,
    decompose_all_conventions,
)
from fsvm.errors import AttributionError

TOLERANCE = 1e-9

#: The fixture stores demand rounded to three decimals so it round trips through
#: CSV byte for byte. That rounding perturbs each per SKU error slightly, so a
#: scenario whose true skill effect is exactly zero measures as a few parts in
#: a hundred million rather than as zero. Pinned by
#: `test_the_numerical_noise_floor_is_six_orders_below_any_reported_effect`.
NOISE_FLOOR = 1e-6


@pytest.mark.parametrize("convention", CONVENTIONS)
def test_every_convention_sums_exactly_to_the_restricted_delta(realistic_split, convention):
    """The bug this pins: an early Paasche form used period one errors in the mix
    term as well as period one weights in the skill term, so the two effects
    double counted the cross product and the decomposition was short by it. An
    inexact decomposition lets a residual masquerade as skill, which is the one
    failure this repository cannot tolerate."""
    result = decompose(realistic_split, convention)
    total = result.skill_effect + result.mix_effect + result.interaction_effect
    assert total == pytest.approx(result.restricted_delta, abs=TOLERANCE)


@pytest.mark.parametrize("convention", CONVENTIONS)
def test_a_pure_mix_shift_reports_no_skill_effect_under_any_convention(pure_mix_split, convention):
    result = decompose(pure_mix_split, convention)
    assert result.skill_effect == pytest.approx(0.0, abs=NOISE_FLOOR)


@pytest.mark.parametrize("convention", CONVENTIONS)
def test_a_pure_mix_shift_attributes_the_whole_change_to_mix(pure_mix_split, convention):
    result = decompose(pure_mix_split, convention)
    assert result.mix_effect + result.interaction_effect == pytest.approx(
        result.restricted_delta, abs=NOISE_FLOOR
    )


@pytest.mark.parametrize("convention", CONVENTIONS)
def test_a_pure_skill_change_reports_no_mix_effect_under_any_convention(
    pure_skill_split, convention
):
    result = decompose(pure_skill_split, convention)
    assert result.mix_effect == pytest.approx(0.0, abs=NOISE_FLOOR)


@pytest.mark.parametrize("convention", CONVENTIONS)
def test_a_pure_skill_change_attributes_the_whole_change_to_skill(pure_skill_split, convention):
    result = decompose(pure_skill_split, convention)
    assert result.skill_effect == pytest.approx(result.restricted_delta, abs=NOISE_FLOOR)


def test_the_degenerate_scenarios_have_nothing_unattributable(pure_mix_split, pure_skill_split):
    for split in (pure_mix_split, pure_skill_split):
        assert len(split.entrants) == 0
        assert len(split.exits) == 0
        assert len(split.zero_actual) == 0


def test_only_the_three_term_convention_reports_a_non_zero_interaction(realistic_split):
    results = decompose_all_conventions(realistic_split)
    assert results["three_term"].interaction_effect != 0.0
    for name in ("laspeyres", "paasche", "shapley"):
        assert results[name].interaction_effect == 0.0


def test_the_shapley_split_lies_between_the_laspeyres_and_paasche_splits(realistic_split):
    results = decompose_all_conventions(realistic_split)
    low = min(results["laspeyres"].skill_effect, results["paasche"].skill_effect)
    high = max(results["laspeyres"].skill_effect, results["paasche"].skill_effect)
    assert low <= results["shapley"].skill_effect <= high


def test_the_conventions_disagree_on_the_realistic_panel(realistic_split):
    spread = convention_spread(decompose_all_conventions(realistic_split))
    assert spread["skill_effect_spread"] > 0.0


def test_the_conventions_agree_exactly_when_the_mix_does_not_move(pure_skill_split):
    spread = convention_spread(decompose_all_conventions(pure_skill_split))
    assert spread["skill_effect_spread"] == pytest.approx(0.0, abs=NOISE_FLOOR)


def test_the_skill_and_mix_spreads_are_equal_because_both_sum_to_a_fixed_total(realistic_split):
    spread = convention_spread(decompose_all_conventions(realistic_split))
    assert spread["skill_effect_spread"] == pytest.approx(spread["mix_effect_spread"])


def test_an_unknown_convention_is_refused_by_name(realistic_split):
    with pytest.raises(AttributionError, match="unknown convention 'oaxaca'"):
        decompose(realistic_split, "oaxaca")


def test_the_spread_of_zero_conventions_is_refused():
    with pytest.raises(AttributionError, match="spread over zero conventions"):
        convention_spread({})


def test_the_unattributable_delta_is_the_gap_between_full_and_restricted_change(realistic_split):
    result = decompose(realistic_split)
    assert result.unattributable_delta == pytest.approx(
        result.total_delta - result.restricted_delta, abs=TOLERANCE
    )


def test_the_unattributable_delta_is_zero_when_no_sku_churns(pure_mix_split):
    result = decompose(pure_mix_split)
    assert result.unattributable_delta == pytest.approx(0.0, abs=TOLERANCE)


def test_the_realistic_panel_leaves_a_real_unattributable_gap(realistic_split):
    result = decompose(realistic_split)
    assert abs(result.unattributable_delta) > 1e-4


def test_mix_share_of_improvement_is_withheld_when_accuracy_got_worse(realistic_split):
    result = decompose(realistic_split)
    flipped = type(result)(**{**result.as_dict(), "total_delta": 0.01})
    assert flipped.mix_share_of_improvement is None


def test_mix_share_of_improvement_is_a_fraction_when_accuracy_improved(realistic_split):
    share = decompose(realistic_split).mix_share_of_improvement
    assert 0.0 < share < 1.0


def test_the_attribution_round_trips_through_a_plain_dictionary(realistic_split):
    result = decompose(realistic_split)
    assert type(result)(**result.as_dict()) == result


def test_the_population_counts_on_the_attribution_match_the_split(realistic_split):
    result = decompose(realistic_split)
    assert result.n_decomposable == len(realistic_split.decomposable)
    assert result.n_entrants == len(realistic_split.entrants)
    assert result.n_exits == len(realistic_split.exits)
    assert result.n_zero_actual == len(realistic_split.zero_actual)


def test_decompose_all_conventions_returns_one_result_per_convention(realistic_split):
    results = decompose_all_conventions(realistic_split)
    assert set(results) == set(CONVENTIONS)


def test_every_convention_agrees_on_the_full_population_wmape(realistic_split):
    results = decompose_all_conventions(realistic_split)
    values = {round(r.wmape_period1, 12) for r in results.values()}
    assert len(values) == 1


def test_the_numerical_noise_floor_is_six_orders_below_any_reported_effect(
    pure_mix_split, pure_skill_split
):
    """The fixture rounds demand to three decimals, so the degenerate scenarios
    recover their planted zero to a few parts in a hundred million rather than
    to machine epsilon. This pins that floor so the README can state it instead
    of claiming an exactness the fixture does not have."""
    residuals = [
        abs(decompose(pure_mix_split).skill_effect),
        abs(decompose(pure_skill_split).mix_effect),
    ]
    assert max(residuals) < 1e-6
    assert max(residuals) * 1e5 < abs(decompose(pure_mix_split).restricted_delta)


def test_the_effect_kernel_refuses_an_unknown_convention_when_called_directly():
    """`_effects` is reached by the bootstrap without going through
    `decompose`'s validation, so it validates for itself rather than trusting
    its only current caller."""
    import numpy as np

    from fsvm.decompose import _effects

    ones = np.array([0.5, 0.5])
    with pytest.raises(AttributionError, match="unknown convention 'bennet'"):
        _effects("bennet", ones, ones, ones, ones)
