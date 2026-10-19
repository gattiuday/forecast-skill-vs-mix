"""The seasonal naive referee, and the week alignment bug it was built around."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fsvm.baseline import beat_rate, densify, seasonal_naive
from fsvm.errors import AttributionError


def test_the_referee_carries_the_value_from_one_season_earlier():
    weeks = list(range(1, 9))
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    naive = seasonal_naive(weeks, values, season=4)
    assert np.isnan(naive[:4]).all()
    assert naive[4:].tolist() == [1.0, 2.0, 3.0, 4.0]


def test_the_referee_never_sees_the_future():
    naive = seasonal_naive([1, 2, 3], [10.0, 20.0, 30.0], season=1)
    assert np.isnan(naive[0])


def test_the_referee_aligns_on_week_number_not_row_position():
    """The bug: a sales extract omits weeks with no sales, so a 52 row shift
    reaches back an arbitrary number of weeks. Here week 6 is missing, so the
    referee for week 9 must be the week 5 value and the referee for week 10
    must be absent, not simply the previous row."""
    weeks = [1, 2, 3, 4, 5, 7, 8, 9, 10]
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 8.0, 9.0, 10.0]
    naive = seasonal_naive(weeks, values, season=4)
    by_week = dict(zip(weeks, naive, strict=True))
    assert by_week[9] == 5.0
    assert np.isnan(by_week[10])
    assert by_week[7] == 3.0


def test_a_positional_shift_would_have_given_the_wrong_answer_for_the_same_series():
    weeks = [1, 2, 3, 4, 5, 7, 8, 9, 10]
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 8.0, 9.0, 10.0])
    positional = np.full(values.shape, np.nan)
    positional[4:] = values[:-4]
    week_aligned = seasonal_naive(weeks, values, season=4)
    assert positional[-1] == 5.0
    assert np.isnan(week_aligned[-1])


def test_a_season_of_zero_is_refused():
    with pytest.raises(AttributionError, match="season must be at least 1"):
        seasonal_naive([1, 2], [1.0, 2.0], season=0)


def test_the_referee_refuses_mismatched_weeks_and_values():
    with pytest.raises(AttributionError, match="differ in length"):
        seasonal_naive([1, 2, 3], [1.0, 2.0])


def test_a_series_shorter_than_one_season_has_no_referee_at_all():
    assert np.isnan(seasonal_naive([1, 2], [1.0, 2.0], season=52)).all()


def test_densify_inserts_the_weeks_a_sales_extract_dropped():
    frame = pd.DataFrame(
        {
            "sku": ["A", "A", "A"],
            "week": [1, 2, 5],
            "actual": [1.0, 2.0, 5.0],
            "forecast": [1.0, 2.0, 5.0],
        }
    )
    dense = densify(frame)
    assert dense["week"].tolist() == [1, 2, 3, 4, 5]
    assert dense["actual"].tolist() == [1.0, 2.0, 0.0, 0.0, 5.0]


def test_densify_flags_the_rows_it_invented_so_they_are_never_scored():
    frame = pd.DataFrame(
        {"sku": ["A", "A"], "week": [1, 3], "actual": [1.0, 3.0], "forecast": [1.0, 3.0]}
    )
    dense = densify(frame)
    assert dense["filled"].tolist() == [False, True, False]


def test_densify_does_not_pad_a_launch_backwards_to_the_start_of_the_panel():
    frame = pd.DataFrame(
        {
            "sku": ["A", "A", "B"],
            "week": [1, 9, 9],
            "actual": [1.0, 1.0, 1.0],
            "forecast": [1.0, 1.0, 1.0],
        }
    )
    dense = densify(frame)
    assert dense[dense["sku"] == "B"]["week"].tolist() == [9]


def test_densify_leaves_a_contiguous_panel_unchanged(tiny_panel):
    dense = densify(tiny_panel)
    assert len(dense) == len(tiny_panel)
    assert not dense["filled"].any()


def test_the_beat_rate_is_a_share_between_zero_and_one(realistic_panel):
    scores = beat_rate(realistic_panel, 53)
    assert 0.0 <= scores["beat_rate_unweighted"] <= 1.0
    assert 0.0 <= scores["beat_rate_volume_weighted"] <= 1.0


def test_the_unweighted_and_volume_weighted_beat_rates_disagree(realistic_panel):
    """The aggregation problem in miniature: the model loses to a carry forward
    on most SKUs while winning on most of the volume. A single portfolio number
    reports only the flattering one."""
    scores = beat_rate(realistic_panel, 53)
    assert scores["beat_rate_volume_weighted"] > scores["beat_rate_unweighted"] + 0.1


def test_a_perfect_forecast_beats_the_referee_on_every_sku(tiny_panel):
    perfect = tiny_panel.assign(forecast=tiny_panel["actual"])
    assert beat_rate(perfect, 53)["beat_rate_unweighted"] == pytest.approx(1.0)


def test_skus_with_too_little_history_are_counted_as_undefined_not_as_losses(realistic_panel):
    scores = beat_rate(realistic_panel, 53)
    assert scores["n_undefined"] > 0
    assert scores["n_scored"] + scores["n_undefined"] == realistic_panel["sku"].nunique()


def test_scoring_is_refused_when_no_sku_has_enough_history(tiny_panel):
    short = tiny_panel[tiny_panel["week"] <= 54]
    with pytest.raises(AttributionError, match="no SKU has enough history"):
        beat_rate(short, 53, season=52)


def test_dropping_zero_sales_rows_no_longer_swings_the_beat_rate_by_double_digits(
    realistic_panel,
):
    """Regression pin for the war story. Under the positional referee this gap
    was 18.9 points. Week alignment plus densification leaves a smaller gap
    that is genuine information loss: the sparse extract simply has fewer weeks
    with a recorded forecast to grade."""
    sparse = realistic_panel[realistic_panel["actual"] > 0].reset_index(drop=True)
    dense_rate = beat_rate(realistic_panel, 53)["beat_rate_unweighted"]
    sparse_rate = beat_rate(sparse, 53)["beat_rate_unweighted"]
    assert abs(dense_rate - sparse_rate) < 0.10


def test_a_sku_whose_referee_is_exact_is_counted_as_undefined_not_as_a_loss():
    """A perfectly seasonal series gives the referee zero error, so MASE divides
    by zero. That SKU carries no information about skill and must be excluded
    rather than scored as an infinite loss."""
    weeks = list(range(1, 105))
    values = [100.0 + 10.0 * (week % 52) for week in weeks]
    frame = pd.DataFrame(
        {"sku": "A", "week": weeks, "actual": values, "forecast": [v * 1.05 for v in values]}
    )
    frame = pd.concat([frame, frame.assign(sku="B")], ignore_index=True)
    with pytest.raises(AttributionError, match="no SKU has enough history"):
        beat_rate(frame, 53, season=52)
