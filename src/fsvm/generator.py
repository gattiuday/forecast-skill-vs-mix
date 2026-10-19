"""A seeded panel generator whose ground truth is known, so the decomposition can be graded.

Validating an attribution tool on real data is circular: the thing you want to
check is the thing you cannot observe. So the fixtures are generated with the
answer planted. Two of the scenarios are degenerate on purpose.

    pure_mix    every SKU's period total forecast is actual * (1 + eps_i) with
                eps_i constant across both periods, so each per SKU percentage
                error is identical in both periods by construction and the true
                skill effect is exactly zero. Only the volume shares move.

    pure_skill  every SKU's period one actual total is scaled to equal its
                period zero total, so the volume shares are identical and the
                true mix effect is exactly zero. Only the errors move.

    realistic   both move, plus launches, discontinuations and zero demand
                periods. No closed form answer exists, which is the point: this
                is the scenario where the convention spread has to be published.

A decomposition that cannot return zero on the two degenerate scenarios is
wrong, and `experiments/exp01_recovery.py` is what says so.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SCENARIOS = ("pure_mix", "pure_skill", "realistic")

#: Per archetype: base weekly volume, seasonal amplitude, intrinsic error scale.
ARCHETYPES = {
    "steady_seasonal": {"base": 420.0, "amplitude": 0.35, "error": 0.06, "intermittent": False},
    "promo_driven": {"base": 180.0, "amplitude": 0.20, "error": 0.17, "intermittent": False},
    "long_tail": {"base": 42.0, "amplitude": 0.12, "error": 0.29, "intermittent": False},
    "intermittent": {"base": 9.0, "amplitude": 0.05, "error": 0.55, "intermittent": True},
}

#: Share of the SKU count assigned to each archetype.
ARCHETYPE_MIX = {
    "steady_seasonal": 0.18,
    "promo_driven": 0.22,
    "long_tail": 0.38,
    "intermittent": 0.22,
}


def _assign_archetypes(n_skus: int, rng: np.random.Generator) -> list[str]:
    names, shares = zip(*ARCHETYPE_MIX.items(), strict=True)
    counts = np.floor(np.array(shares) * n_skus).astype(int)
    counts[0] += n_skus - counts.sum()
    assigned = [name for name, count in zip(names, counts, strict=True) for _ in range(count)]
    rng.shuffle(assigned)
    return assigned


def _weekly_volume(
    archetype: str, weeks: np.ndarray, level: float, rng: np.random.Generator
) -> np.ndarray:
    spec = ARCHETYPES[archetype]
    season = 1.0 + spec["amplitude"] * np.sin(2.0 * np.pi * (weeks % 52) / 52.0)
    noise = rng.normal(1.0, 0.09, size=weeks.size)
    volume = level * season * noise
    if spec["intermittent"]:
        active = rng.random(weeks.size) < 0.38
        volume = np.where(active, volume * 2.6, 0.0)
    return np.clip(volume, 0.0, None)


def generate_panel(
    n_skus: int = 240,
    weeks: int = 104,
    split_week: int = 53,
    scenario: str = "realistic",
    seed: int = 20260419,
    churn_share: float = 0.12,
) -> pd.DataFrame:
    """Generate a tidy weekly panel with columns sku, week, actual, forecast.

    `churn_share` is the share of SKUs that exist in only one of the two
    periods, split evenly between launches and discontinuations. It is zero for
    the degenerate scenarios, because a launch has no counterfactual and would
    make "the true skill effect is exactly zero" false.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario '{scenario}'; expected one of {', '.join(SCENARIOS)}")
    if weeks < 2 * 52:
        raise ValueError("at least 104 weeks are needed for a 52 week seasonal referee to exist")
    if not 0.0 <= churn_share < 0.5:
        raise ValueError(f"churn_share must be in [0, 0.5), got {churn_share}")

    rng = np.random.default_rng(seed)
    archetypes = _assign_archetypes(n_skus, rng)
    week_index = np.arange(1, weeks + 1)
    is_period1 = week_index >= split_week

    if scenario in ("pure_mix", "pure_skill"):
        churn_share = 0.0

    n_churn = round(churn_share * n_skus)
    launches = set(range(n_churn // 2))
    discontinued = set(range(n_churn // 2, n_churn))
    # Seasonal items that go dormant for a whole period: present in both
    # periods, zero demand in one, so a per SKU percentage error has no
    # denominator. Real catalogues are full of these and they are the
    # population most often silently dropped.
    dormant = (
        set(range(n_churn, n_churn + max(1, round(0.05 * n_skus))))
        if scenario == "realistic"
        else set()
    )

    frames = []
    for sku_id, archetype in enumerate(archetypes):
        spec = ARCHETYPES[archetype]
        level = spec["base"] * float(rng.lognormal(0.0, 0.42))
        volume = _weekly_volume(archetype, week_index, level, rng)

        # The planted mix shift: period one volume moves toward the forecastable
        # archetypes and away from the intermittent tail. This is what makes the
        # portfolio WMAPE improve without anyone forecasting better.
        if scenario in ("pure_mix", "realistic"):
            tilt = {
                "steady_seasonal": 1.55,
                "promo_driven": 1.12,
                "long_tail": 0.88,
                "intermittent": 0.45,
            }[archetype]
            volume = np.where(is_period1, volume * tilt, volume)

        eps0 = float(rng.normal(0.0, spec["error"]))
        if scenario == "pure_mix":
            eps1 = eps0
        else:
            # The planted skill change: a small broad improvement, cancelled on
            # the hard archetypes where the model actually regressed.
            drift = -0.18 if archetype in ("steady_seasonal", "promo_driven") else 0.26
            eps1 = eps0 * (1.0 + drift)

        if scenario == "pure_skill":
            # Force identical period volume shares by rescaling period one to
            # match each SKU's own period zero total.
            total0 = volume[~is_period1].sum()
            total1 = volume[is_period1].sum()
            if total1 > 0 and total0 > 0:
                volume = np.where(is_period1, volume * (total0 / total1), volume)

        forecast = np.where(is_period1, volume * (1.0 + eps1), volume * (1.0 + eps0))
        if scenario == "realistic":
            forecast = forecast + rng.normal(0.0, 0.22 * max(level, 1.0), size=weeks)
        forecast = np.clip(forecast, 0.0, None)

        if sku_id in dormant:
            dormant_in_period1 = sku_id % 2 == 0
            silence = is_period1 if dormant_in_period1 else ~is_period1
            volume = np.where(silence, 0.0, volume)
            forecast = np.where(silence, forecast * 0.3, forecast)

        keep = np.ones(weeks, dtype=bool)
        if sku_id in launches:
            keep = is_period1
        elif sku_id in discontinued:
            keep = ~is_period1

        frames.append(
            pd.DataFrame(
                {
                    "sku": f"SKU-{sku_id:04d}",
                    "week": week_index[keep],
                    "archetype": archetype,
                    "actual": np.round(volume[keep], 3),
                    "forecast": np.round(forecast[keep], 3),
                }
            )
        )

    panel = pd.concat(frames, ignore_index=True)
    return panel.sort_values(["sku", "week"], ignore_index=True)
