"""The bootstrap interval, and what it refuses to claim."""

from __future__ import annotations

import pytest

from fsvm.resample import skill_effect_interval


def test_the_interval_brackets_the_point_estimate(realistic_split):
    from fsvm.decompose import decompose

    point = decompose(realistic_split).skill_effect
    interval = skill_effect_interval(realistic_split, samples=600)
    assert interval["skill_effect_ci_low"] <= point <= interval["skill_effect_ci_high"]


def test_the_interval_is_reproducible_for_a_fixed_seed(realistic_split):
    first = skill_effect_interval(realistic_split, samples=400, seed=11)
    second = skill_effect_interval(realistic_split, samples=400, seed=11)
    assert first == second


def test_a_different_seed_moves_the_interval(realistic_split):
    first = skill_effect_interval(realistic_split, samples=400, seed=11)
    second = skill_effect_interval(realistic_split, samples=400, seed=12)
    assert first["skill_effect_ci_low"] != second["skill_effect_ci_low"]


def test_a_wider_confidence_level_gives_a_wider_interval(realistic_split):
    narrow = skill_effect_interval(realistic_split, samples=900, level=0.50, seed=5)
    wide = skill_effect_interval(realistic_split, samples=900, level=0.99, seed=5)
    narrow_width = narrow["skill_effect_ci_high"] - narrow["skill_effect_ci_low"]
    wide_width = wide["skill_effect_ci_high"] - wide["skill_effect_ci_low"]
    assert wide_width > narrow_width


def test_a_real_skill_effect_produces_an_interval_that_excludes_zero(pure_skill_split):
    interval = skill_effect_interval(pure_skill_split, samples=800)
    assert interval["contains_zero"] is False


def test_a_pure_mix_shift_produces_an_interval_that_contains_zero(pure_mix_split):
    """The honest half of the tool: when there was no skill change, the interval
    must say so rather than reporting a tiny effect with confidence."""
    interval = skill_effect_interval(pure_mix_split, samples=800)
    assert interval["contains_zero"] is True


def test_the_interval_reports_how_many_resamples_actually_contributed(realistic_split):
    interval = skill_effect_interval(realistic_split, samples=300)
    assert interval["bootstrap_samples"] <= 300
    assert interval["bootstrap_samples"] > 150


@pytest.mark.parametrize("convention", ["laspeyres", "paasche", "three_term", "shapley"])
def test_the_interval_can_be_computed_for_any_convention(realistic_split, convention):
    interval = skill_effect_interval(realistic_split, convention, samples=200)
    assert interval["skill_effect_ci_low"] < interval["skill_effect_ci_high"]
