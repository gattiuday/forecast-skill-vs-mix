# ADR-004: Align the seasonal referee on week numbers, and densify before scoring

Status: accepted, after a bug

## Context

The seasonal naive referee compares a forecast against the actual from one season
earlier. The first implementation did that with a positional shift: `values[:-52]`
placed at `[52:]`.

That is correct only when every SKU has a row for every week. Sales extracts from an
ERP system routinely do not: a row exists where a transaction exists, so a slow moving
SKU has gaps, and a 52 row shift reaches back an arbitrary number of calendar weeks
that varies per SKU.

The measurement, from `experiments/exp06_extract_format.py`: dropping zero sales rows
from this repository's own fixture, which is exactly what a sparse extract looks like,
moved the unweighted beat rate by 18.9 points under the positional referee.

The failure is quiet. The code raises nothing, the output looks reasonable, and the
number is wrong by an amount that depends on how the upstream extract was written.

## Decision

Two changes:

1. **Align on week number.** `seasonal_naive` takes weeks and values, builds a week to
   value lookup, and returns the value from `week - season` or NaN where that week is
   absent. A missing predecessor is NaN rather than a nearby value.
2. **Densify before scoring.** `densify` inserts a zero demand row for every week a SKU
   is missing inside its own observed span, and flags those rows. The inserted rows
   inform the referee but are never scored, so a forecast is only graded where one was
   actually recorded.

Padding is bounded by each SKU's own first and last observed week. Padding a launch
backwards to the start of the panel would invent history.

## The assumption this makes explicit

Densifying treats a missing week as zero demand rather than as missing data. That is a
statement about the upstream system, not a fact about the data. It is true of a sales
transaction extract and false of, for example, a shipment file where a SKU disappears
during a system migration.

The assumption lives in one named function with this ADR attached rather than being
spread through the scoring code, so a user whose extract behaves differently has one
place to change and one paragraph to read.

## Consequences

After the fix the same comparison moves the beat rate by 4.8 points rather than 18.9.
The remaining gap is not a bug: a sparse extract genuinely carries fewer weeks with a
recorded forecast, so 12 SKUs fall below the minimum scored week count and drop out.
That is information loss in the extract, which the tool reports as `n_undefined` rather
than hiding in the rate.

The superseded positional implementation is kept in `experiments/exp06_extract_format.py`
so the size of the bug can be re-measured rather than remembered, and
`test_dropping_zero_sales_rows_no_longer_swings_the_beat_rate_by_double_digits` fails
if anything reintroduces it.
