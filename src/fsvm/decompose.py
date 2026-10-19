"""Shift share attribution of a WMAPE change, in four conventions, with the gap left visible.

WMAPE over a population is sum_i w_i * e_i, with w_i the volume share and e_i
the per SKU absolute percentage error. A change in that quantity between two
periods therefore has two proximate causes: the e_i moved (skill) and the w_i
moved (mix). Separating them requires choosing which period's values to hold
constant while varying the other, and that choice is not determined by the data.

Four conventions are implemented because they disagree, and the size of their
disagreement is a property of the panel worth publishing. A tool that reports
one number here is not more accurate than one that reports four, it is just
quieter about the arbitrary step.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from fsvm.config import CONVENTIONS, DEFAULT_CONVENTION
from fsvm.errors import AttributionError
from fsvm.panel import PopulationSplit

__all__ = ["Attribution", "convention_spread", "decompose", "decompose_all_conventions"]


@dataclass(frozen=True)
class Attribution:
    """One decomposition of one WMAPE change.

    All effects are in WMAPE points, signed so that a negative number means the
    effect pushed WMAPE down, which is an improvement. The three total_* fields
    describe the full population; the restricted_delta is the part the effects
    actually sum to.
    """

    convention: str
    wmape_period0: float
    wmape_period1: float
    total_delta: float
    restricted_wmape_period0: float
    restricted_wmape_period1: float
    restricted_delta: float
    skill_effect: float
    mix_effect: float
    interaction_effect: float
    unattributable_delta: float
    unattributable_volume_share: float
    n_decomposable: int
    n_entrants: int
    n_exits: int
    n_zero_actual: int

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def mix_share_of_improvement(self) -> float | None:
        """Share of a WMAPE improvement attributable to mix rather than skill.

        Returns None when WMAPE did not improve, because the ratio is then a
        share of a worsening and reads as its own opposite. Callers that want a
        number regardless should ask for the effects directly.
        """
        if self.total_delta >= 0:
            return None
        mix_like = self.mix_effect + self.interaction_effect
        return float(mix_like / self.total_delta)


def _weights_and_errors(split: PopulationSplit) -> tuple[np.ndarray, ...]:
    rows = split.totals.loc[split.decomposable]
    a0 = rows["a0"].to_numpy(dtype=float)
    a1 = rows["a1"].to_numpy(dtype=float)
    f0 = rows["f0"].to_numpy(dtype=float)
    f1 = rows["f1"].to_numpy(dtype=float)
    if a0.sum() <= 0 or a1.sum() <= 0:
        raise AttributionError("the decomposable population has no demand in one of the periods")
    w0 = a0 / a0.sum()
    w1 = a1 / a1.sum()
    e0 = np.abs(a0 - f0) / a0
    e1 = np.abs(a1 - f1) / a1
    return w0, w1, e0, e1


def _effects(convention: str, w0, w1, e0, e1) -> tuple[float, float, float]:
    """Return (skill, mix, interaction) for one convention.

    Each convention is exact: the three returned effects sum to the restricted
    delta to floating point tolerance. That is asserted by a test for all four,
    because an inexact decomposition would let a residual masquerade as skill.
    """
    dw = w1 - w0
    de = e1 - e0
    if convention == "laspeyres":
        # Hold mix at period zero for the skill term, so the mix term carries
        # the interaction. This is the convention a planner reaches for by
        # default, and it systematically overstates mix when the two move together.
        return float(w0 @ de), float(dw @ e1), 0.0
    if convention == "paasche":
        # The mirror image: hold mix at period one, mix term priced at old errors.
        return float(w1 @ de), float(dw @ e0), 0.0
    if convention == "three_term":
        # Keep the cross term visible rather than assigning it to either side.
        return float(w0 @ de), float(dw @ e0), float(dw @ de)
    if convention == "shapley":
        # Symmetric in the two periods: the cross term is split evenly, which is
        # the Shapley value of the two factor game. See ADR-002.
        return float(((w0 + w1) / 2.0) @ de), float(dw @ ((e0 + e1) / 2.0)), 0.0
    raise AttributionError(
        f"unknown convention '{convention}'; expected one of {', '.join(CONVENTIONS)}"
    )


def decompose(split: PopulationSplit, convention: str = DEFAULT_CONVENTION) -> Attribution:
    """Decompose the WMAPE change for one convention."""
    if convention not in CONVENTIONS:
        raise AttributionError(
            f"unknown convention '{convention}'; expected one of {', '.join(CONVENTIONS)}"
        )
    w0, w1, e0, e1 = _weights_and_errors(split)
    skill, mix, interaction = _effects(convention, w0, w1, e0, e1)

    restricted0 = float(w0 @ e0)
    restricted1 = float(w1 @ e1)

    full = split.totals
    if full["a0"].sum() <= 0 or full["a1"].sum() <= 0:
        raise AttributionError("the full population has no demand in one of the periods")
    full0 = float(np.abs(full["a0"] - full["f0"]).sum() / full["a0"].sum())
    full1 = float(np.abs(full["a1"] - full["f1"]).sum() / full["a1"].sum())

    total_delta = full1 - full0
    restricted_delta = restricted1 - restricted0

    return Attribution(
        convention=convention,
        wmape_period0=full0,
        wmape_period1=full1,
        total_delta=total_delta,
        restricted_wmape_period0=restricted0,
        restricted_wmape_period1=restricted1,
        restricted_delta=restricted_delta,
        skill_effect=skill,
        mix_effect=mix,
        interaction_effect=interaction,
        unattributable_delta=total_delta - restricted_delta,
        unattributable_volume_share=split.unattributable_volume_share(),
        n_decomposable=len(split.decomposable),
        n_entrants=len(split.entrants),
        n_exits=len(split.exits),
        n_zero_actual=len(split.zero_actual),
    )


def decompose_all_conventions(split: PopulationSplit) -> dict[str, Attribution]:
    """Run every convention, so the report can show the spread rather than a pick."""
    return {name: decompose(split, name) for name in CONVENTIONS}


def convention_spread(results: dict[str, Attribution]) -> dict[str, float]:
    """Range of each effect across conventions, in WMAPE points.

    This is the number that says how much of the answer is a modelling choice
    rather than a measurement. If the mix spread is comparable to the mix effect
    itself, the honest statement is that the split is not determined.
    """
    if not results:
        raise AttributionError("cannot compute a spread over zero conventions")
    out = {}
    for field_name in ("skill_effect", "mix_effect"):
        values = [getattr(result, field_name) for result in results.values()]
        out[f"{field_name}_min"] = float(min(values))
        out[f"{field_name}_max"] = float(max(values))
        out[f"{field_name}_spread"] = float(max(values) - min(values))
    return out
