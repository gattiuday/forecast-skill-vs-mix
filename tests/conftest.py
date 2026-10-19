"""Shared fixtures. Everything here is deterministic; no test may touch the network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fsvm.generator import generate_panel
from fsvm.panel import split_populations, to_period_totals, validate_panel

SPLIT_WEEK = 53


@pytest.fixture(scope="session")
def realistic_panel() -> pd.DataFrame:
    return validate_panel(generate_panel(scenario="realistic"))


@pytest.fixture(scope="session")
def pure_mix_panel() -> pd.DataFrame:
    return validate_panel(generate_panel(scenario="pure_mix"))


@pytest.fixture(scope="session")
def pure_skill_panel() -> pd.DataFrame:
    return validate_panel(generate_panel(scenario="pure_skill"))


@pytest.fixture(scope="session")
def realistic_split(realistic_panel):
    return split_populations(to_period_totals(realistic_panel, SPLIT_WEEK))


@pytest.fixture(scope="session")
def pure_mix_split(pure_mix_panel):
    return split_populations(to_period_totals(pure_mix_panel, SPLIT_WEEK))


@pytest.fixture(scope="session")
def pure_skill_split(pure_skill_panel):
    return split_populations(to_period_totals(pure_skill_panel, SPLIT_WEEK))


@pytest.fixture
def tiny_panel() -> pd.DataFrame:
    """A four SKU, 104 week panel small enough to reason about by hand."""
    rows = []
    rng = np.random.default_rng(7)
    for sku in range(4):
        for week in range(1, 105):
            actual = 100.0 + 10.0 * sku + float(rng.normal(0, 3))
            rows.append(
                {
                    "sku": f"S{sku}",
                    "week": week,
                    "actual": round(actual, 3),
                    "forecast": round(actual * 1.1, 3),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def fixture_csv(tmp_path, realistic_panel):
    path = tmp_path / "panel.csv"
    realistic_panel.to_csv(path, index=False)
    return path
