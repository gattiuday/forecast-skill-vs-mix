"""Loading a demand panel and splitting its SKUs into the four populations that matter.

The decomposition in `decompose` is only defined on SKUs that exist in both
periods with positive demand in both. Every other SKU is real, carries real
volume, and is structurally undecomposable. This module names those groups
instead of dropping them, because the size of the group it cannot explain is
the honest part of the output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from fsvm.config import DEFAULTS
from fsvm.errors import AttributionError, InsufficientOverlap

REQUIRED_COLUMNS = ("sku", "week", "actual", "forecast")


@dataclass(frozen=True)
class PopulationSplit:
    """The four SKU populations in a two period comparison.

    decomposable
        Present in both periods with positive actual demand in both. The only
        group a shift share decomposition is defined on.
    entrants
        Present in period one only. A launch has no period zero error, so there
        is no counterfactual to hold anything constant against.
    exits
        Present in period zero only. Same problem, mirrored.
    zero_actual
        Present in both periods but with zero demand in at least one. A per SKU
        percentage error needs a non zero denominator; these have none.
    """

    totals: pd.DataFrame
    decomposable: pd.Index
    entrants: pd.Index
    exits: pd.Index
    zero_actual: pd.Index
    meta: dict = field(default_factory=dict)

    @property
    def n_decomposable(self) -> int:
        return len(self.decomposable)

    def unattributable_volume_share(self) -> float:
        """Share of total actual volume across both periods that cannot be decomposed.

        Reported as a share of volume rather than of SKU count on purpose. A
        thousand churning micro SKUs matter less than two churning large ones,
        and a count would say the opposite.
        """
        total = self.totals[["a0", "a1"]].to_numpy().sum()
        if total <= 0:
            raise AttributionError("the panel contains no positive demand in either period")
        kept = self.totals.loc[self.decomposable, ["a0", "a1"]].to_numpy().sum()
        return float(1.0 - kept / total)


def load_panel(path: str | Path) -> pd.DataFrame:
    """Read a tidy demand panel from CSV and validate it before anything touches it.

    Validation happens here rather than at the point of use so that a malformed
    file produces one clear message instead of a numpy broadcasting error three
    modules later.
    """
    frame = pd.read_csv(path)
    return validate_panel(frame)


def validate_panel(frame: pd.DataFrame) -> pd.DataFrame:
    """Check column presence, types and sign, and return a normalised copy."""
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise AttributionError(f"panel is missing required columns: {', '.join(missing)}")
    out = frame.copy()
    for column in ("actual", "forecast"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any():
            raise AttributionError(f"column '{column}' contains values that are not numbers")
    out["week"] = pd.to_numeric(out["week"], errors="coerce").astype("Int64")
    if out["week"].isna().any():
        raise AttributionError("column 'week' contains values that are not integers")
    out["week"] = out["week"].astype(int)
    if (out["actual"] < 0).any():
        raise AttributionError("negative actual demand is not supported; net returns out upstream")
    if out.duplicated(subset=["sku", "week"]).any():
        offenders = out[out.duplicated(subset=["sku", "week"], keep=False)]["sku"].unique()[:5]
        raise AttributionError(
            f"panel has more than one row per sku and week, for example: {list(offenders)}"
        )
    return out


def to_period_totals(frame: pd.DataFrame, split_week: int) -> pd.DataFrame:
    """Aggregate weekly rows into two period totals per SKU.

    Aggregating before computing errors is a deliberate choice, not a shortcut.
    Errors computed weekly and then averaged answer a different question from
    errors computed on period totals, and the planning conversation this tool
    supports is about period totals. ADR-003 records what that choice gives up.
    """
    if split_week <= int(frame["week"].min()) or split_week > int(frame["week"].max()):
        raise AttributionError(
            f"split_week {split_week} lies outside the panel range "
            f"{int(frame['week'].min())} to {int(frame['week'].max())}"
        )
    period = np.where(frame["week"] < split_week, 0, 1)
    tagged = frame.assign(period=period)
    wide = tagged.pivot_table(
        index="sku", columns="period", values=["actual", "forecast"], aggfunc="sum"
    )
    totals = pd.DataFrame(index=wide.index)
    for source, target in (("actual", "a"), ("forecast", "f")):
        for period_id in (0, 1):
            column = (source, period_id)
            totals[f"{target}{period_id}"] = wide[column] if column in wide.columns else np.nan
    totals.index.name = "sku"
    return totals


def split_populations(
    totals: pd.DataFrame, min_overlap: int = DEFAULTS.min_overlap_skus
) -> PopulationSplit:
    """Partition SKUs into decomposable, entrants, exits and zero actual.

    The default comes from `config.Thresholds`. It was a duplicated literal
    until a re-audit pointed out that `min_overlap_skus` was documented in the
    config and read by nothing, so changing it there changed nothing. A config
    entry that nobody reads is worse than a plain literal, because it tells a
    reviewer the knob works.
    """
    present0 = totals["a0"].notna()
    present1 = totals["a1"].notna()
    both = present0 & present1
    positive = both & (totals["a0"].fillna(0) > 0) & (totals["a1"].fillna(0) > 0)

    decomposable = totals.index[positive]
    entrants = totals.index[~present0 & present1]
    exits = totals.index[present0 & ~present1]
    zero_actual = totals.index[both & ~positive]

    if len(decomposable) < min_overlap:
        raise InsufficientOverlap(
            f"only {len(decomposable)} SKUs appear in both periods with positive demand, "
            f"below the minimum of {min_overlap}; no attribution is defined on this panel"
        )
    return PopulationSplit(
        totals=totals.fillna(0.0),
        decomposable=decomposable,
        entrants=entrants,
        exits=exits,
        zero_actual=zero_actual,
        meta={"min_overlap": min_overlap, "n_skus": len(totals)},
    )
