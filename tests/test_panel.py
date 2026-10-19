"""Validation, period aggregation, and the four way population split."""

from __future__ import annotations

import pandas as pd
import pytest

from fsvm.errors import AttributionError, InsufficientOverlap
from fsvm.panel import (
    load_panel,
    split_populations,
    to_period_totals,
    validate_panel,
)


def _frame(rows):
    return pd.DataFrame(rows, columns=["sku", "week", "actual", "forecast"])


def test_validate_names_every_missing_column_at_once():
    with pytest.raises(AttributionError, match="actual, forecast"):
        validate_panel(pd.DataFrame({"sku": ["A"], "week": [1]}))


def test_validate_rejects_non_numeric_actuals():
    with pytest.raises(AttributionError, match="'actual' contains values that are not numbers"):
        validate_panel(_frame([("A", 1, "many", 3.0)]))


def test_validate_rejects_non_numeric_weeks():
    with pytest.raises(AttributionError, match="'week' contains values that are not integers"):
        validate_panel(_frame([("A", "early", 1.0, 3.0)]))


def test_validate_rejects_negative_demand_rather_than_clipping_it():
    with pytest.raises(AttributionError, match="negative actual demand"):
        validate_panel(_frame([("A", 1, -2.0, 3.0)]))


def test_validate_rejects_duplicate_sku_week_rows_and_names_an_offender():
    with pytest.raises(AttributionError, match="more than one row per sku and week"):
        validate_panel(_frame([("A", 1, 1.0, 1.0), ("A", 1, 2.0, 2.0)]))


def test_validate_returns_a_copy_and_leaves_the_caller_frame_untouched():
    original = _frame([("A", 1, 1.0, 1.0)])
    validated = validate_panel(original)
    validated.loc[0, "actual"] = 999.0
    assert original.loc[0, "actual"] == 1.0


def test_load_panel_reads_a_csv_and_validates_it(tmp_path):
    path = tmp_path / "p.csv"
    _frame([("A", 1, 1.0, 1.0)]).to_csv(path, index=False)
    assert len(load_panel(path)) == 1


def test_load_panel_rejects_a_bad_csv_with_a_domain_error(tmp_path):
    path = tmp_path / "p.csv"
    _frame([("A", 1, -1.0, 1.0)]).to_csv(path, index=False)
    with pytest.raises(AttributionError):
        load_panel(path)


def test_period_totals_sum_weekly_rows_within_each_period():
    frame = validate_panel(_frame([("A", 1, 10.0, 11.0), ("A", 2, 20.0, 19.0), ("A", 3, 5.0, 6.0)]))
    totals = to_period_totals(frame, split_week=3)
    assert totals.loc["A", "a0"] == pytest.approx(30.0)
    assert totals.loc["A", "a1"] == pytest.approx(5.0)
    assert totals.loc["A", "f0"] == pytest.approx(30.0)


def test_a_split_week_outside_the_panel_range_is_rejected():
    frame = validate_panel(_frame([("A", 1, 1.0, 1.0), ("A", 2, 1.0, 1.0)]))
    with pytest.raises(AttributionError, match="lies outside the panel range"):
        to_period_totals(frame, split_week=99)


def test_a_split_week_at_the_very_start_is_rejected_because_period_zero_would_be_empty():
    frame = validate_panel(_frame([("A", 1, 1.0, 1.0), ("A", 2, 1.0, 1.0)]))
    with pytest.raises(AttributionError, match="lies outside the panel range"):
        to_period_totals(frame, split_week=1)


def test_a_sku_absent_from_period_zero_is_classified_as_an_entrant(realistic_split):
    assert len(realistic_split.entrants) > 0
    for sku in realistic_split.entrants:
        assert realistic_split.totals.loc[sku, "a0"] == 0.0


def test_a_sku_absent_from_period_one_is_classified_as_an_exit(realistic_split):
    assert len(realistic_split.exits) > 0
    for sku in realistic_split.exits:
        assert realistic_split.totals.loc[sku, "a1"] == 0.0


def test_a_sku_present_in_both_periods_with_no_demand_in_one_is_classified_as_zero_actual(
    realistic_split,
):
    assert len(realistic_split.zero_actual) > 0


def test_the_four_populations_partition_the_catalogue_exactly(realistic_split):
    total = (
        len(realistic_split.decomposable)
        + len(realistic_split.entrants)
        + len(realistic_split.exits)
        + len(realistic_split.zero_actual)
    )
    assert total == len(realistic_split.totals)


def test_the_four_populations_do_not_overlap(realistic_split):
    groups = [
        set(realistic_split.decomposable),
        set(realistic_split.entrants),
        set(realistic_split.exits),
        set(realistic_split.zero_actual),
    ]
    for index, left in enumerate(groups):
        for right in groups[index + 1 :]:
            assert not left & right


def test_an_attribution_is_refused_when_too_few_skus_appear_in_both_periods():
    frame = validate_panel(
        _frame([("A", 1, 10.0, 10.0), ("A", 2, 10.0, 10.0), ("B", 1, 5.0, 5.0), ("B", 2, 5.0, 5.0)])
    )
    with pytest.raises(InsufficientOverlap, match="below the minimum"):
        split_populations(to_period_totals(frame, split_week=2), min_overlap=30)


def test_the_overlap_floor_can_be_lowered_for_a_deliberately_small_panel():
    frame = validate_panel(
        _frame([("A", 1, 10.0, 10.0), ("A", 2, 10.0, 10.0), ("B", 1, 5.0, 5.0), ("B", 2, 5.0, 5.0)])
    )
    split = split_populations(to_period_totals(frame, split_week=2), min_overlap=2)
    assert split.n_decomposable == 2


def test_unattributable_volume_is_reported_as_a_share_of_volume_not_of_sku_count(realistic_split):
    share = realistic_split.unattributable_volume_share()
    count_share = 1.0 - len(realistic_split.decomposable) / len(realistic_split.totals)
    assert 0.0 < share < 1.0
    assert share != pytest.approx(count_share)


def test_unattributable_volume_is_zero_when_every_sku_spans_both_periods(tiny_panel):
    split = split_populations(to_period_totals(validate_panel(tiny_panel), 53), min_overlap=2)
    assert split.unattributable_volume_share() == pytest.approx(0.0)


def test_every_decomposable_sku_has_positive_demand_in_both_periods(realistic_split):
    """Pins the invariant that let three dead guards be deleted from
    `decompose` and `resample`. If this ever fails, those guards have to come
    back, because a zero denominator would otherwise reach the arithmetic."""
    rows = realistic_split.totals.loc[realistic_split.decomposable]
    assert (rows["a0"] > 0).all()
    assert (rows["a1"] > 0).all()


def test_an_empty_catalogue_cannot_report_an_unattributable_share():
    import pandas as pd

    from fsvm.panel import PopulationSplit

    empty = pd.DataFrame(
        {"a0": [0.0], "a1": [0.0], "f0": [0.0], "f1": [0.0]}, index=pd.Index(["A"], name="sku")
    )
    split = PopulationSplit(empty, pd.Index([]), pd.Index([]), pd.Index([]), pd.Index(["A"]))
    with pytest.raises(AttributionError, match="no positive demand in either period"):
        split.unattributable_volume_share()
