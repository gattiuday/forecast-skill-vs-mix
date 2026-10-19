"""Properties of the accuracy metrics, and the identity the decomposition depends on."""

from __future__ import annotations

import numpy as np
import pytest

from fsvm.metrics import (
    bias,
    mape,
    mase,
    sku_ape,
    volume_shares,
    weighted_mean_identity,
    wmape,
)


def test_wmape_is_zero_for_a_perfect_forecast():
    assert wmape([5.0, 10.0], [5.0, 10.0]) == 0.0


def test_wmape_equals_the_volume_weighted_mean_of_per_sku_errors():
    actual = [10.0, 20.0, 30.0, 7.5]
    forecast = [12.0, 18.0, 33.0, 6.0]
    assert wmape(actual, forecast) == pytest.approx(weighted_mean_identity(actual, forecast))


def test_the_weighted_mean_identity_holds_on_a_large_random_population():
    rng = np.random.default_rng(1)
    actual = rng.uniform(1.0, 500.0, size=400)
    forecast = actual * rng.uniform(0.4, 1.8, size=400)
    assert wmape(actual, forecast) == pytest.approx(weighted_mean_identity(actual, forecast))


def test_wmape_weights_a_large_sku_more_than_a_small_one():
    small_error_on_big_sku = wmape([1000.0, 10.0], [1100.0, 10.0])
    same_error_on_small_sku = wmape([1000.0, 10.0], [1000.0, 11.0])
    assert small_error_on_big_sku > same_error_on_small_sku


def test_wmape_is_undefined_when_total_demand_is_zero():
    with pytest.raises(ValueError, match="undefined when total actual demand is zero"):
        wmape([0.0, 0.0], [5.0, 5.0])


def test_wmape_rejects_negative_actuals_rather_than_absorbing_them():
    with pytest.raises(ValueError, match="negative actuals"):
        wmape([-5.0, 10.0], [5.0, 10.0])


def test_wmape_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="lengths differ"):
        wmape([1.0, 2.0], [1.0])


def test_wmape_rejects_an_empty_series():
    with pytest.raises(ValueError, match="empty series"):
        wmape([], [])


def test_wmape_rejects_non_finite_values():
    with pytest.raises(ValueError, match="finite"):
        wmape([1.0, float("nan")], [1.0, 2.0])


def test_wmape_rejects_a_two_dimensional_input():
    with pytest.raises(ValueError, match="one dimensional"):
        wmape([[1.0, 2.0]], [[1.0, 2.0]])


def test_mape_ignores_skus_with_zero_actual_rather_than_dividing_by_zero():
    assert mape([0.0, 10.0], [5.0, 11.0]) == pytest.approx(0.1)


def test_mape_is_undefined_when_every_actual_is_zero():
    with pytest.raises(ValueError, match="every actual is zero"):
        mape([0.0, 0.0], [1.0, 1.0])


def test_mape_and_wmape_disagree_when_the_small_sku_is_the_inaccurate_one():
    actual = [1000.0, 5.0]
    forecast = [1000.0, 10.0]
    assert mape(actual, forecast) > wmape(actual, forecast)


def test_bias_is_positive_when_the_forecast_is_too_high():
    assert bias([100.0], [110.0]) == pytest.approx(0.1)


def test_bias_is_negative_when_the_forecast_is_too_low():
    assert bias([100.0], [90.0]) == pytest.approx(-0.1)


def test_bias_cancels_where_wmape_does_not():
    actual = [100.0, 100.0]
    forecast = [120.0, 80.0]
    assert bias(actual, forecast) == pytest.approx(0.0)
    assert wmape(actual, forecast) == pytest.approx(0.2)


def test_bias_is_undefined_when_total_demand_is_zero():
    with pytest.raises(ValueError, match="bias is undefined"):
        bias([0.0], [1.0])


def test_sku_ape_returns_a_mask_naming_the_skus_it_could_not_score():
    errors, defined = sku_ape([0.0, 10.0, 20.0], [1.0, 11.0, 18.0])
    assert defined.tolist() == [False, True, True]
    assert errors == pytest.approx([0.1, 0.1])


def test_volume_shares_sum_to_one():
    assert volume_shares([1.0, 3.0, 6.0]).sum() == pytest.approx(1.0)


def test_volume_shares_are_undefined_without_demand():
    with pytest.raises(ValueError, match="volume shares are undefined"):
        volume_shares([0.0, 0.0])


def test_the_weighted_mean_identity_refuses_populations_containing_a_zero_actual():
    with pytest.raises(ValueError, match="every actual is positive"):
        weighted_mean_identity([0.0, 10.0], [1.0, 10.0])


def test_mase_below_one_means_the_forecast_beat_the_referee():
    actual = [10.0, 12.0, 14.0]
    good = [10.5, 12.5, 13.5]
    naive = [8.0, 15.0, 10.0]
    assert mase(actual, good, naive) < 1.0


def test_mase_above_one_means_the_referee_won():
    actual = [10.0, 12.0, 14.0]
    poor = [1.0, 30.0, 2.0]
    naive = [10.5, 11.5, 14.5]
    assert mase(actual, poor, naive) > 1.0


def test_mase_is_undefined_against_an_exact_referee():
    with pytest.raises(ValueError, match="perfectly seasonal"):
        mase([1.0, 2.0], [1.5, 2.5], [1.0, 2.0])


def test_mase_rejects_a_referee_of_the_wrong_length():
    with pytest.raises(ValueError, match="does not match"):
        mase([1.0, 2.0], [1.0, 2.0], [1.0])
