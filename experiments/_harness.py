"""Shared plumbing for the experiments: deterministic setup, JSON output, a printed table."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fsvm.generator import generate_panel
from fsvm.panel import PopulationSplit, split_populations, to_period_totals, validate_panel

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "experiments"
SPLIT_WEEK = 53


def panel(scenario: str = "realistic", **kwargs) -> pd.DataFrame:
    return validate_panel(generate_panel(scenario=scenario, **kwargs))


def split_for(scenario: str = "realistic", **kwargs) -> PopulationSplit:
    return split_populations(to_period_totals(panel(scenario, **kwargs), SPLIT_WEEK))


def subset(split: PopulationSplit, skus) -> PopulationSplit:
    """A PopulationSplit restricted to a subset of the decomposable SKUs.

    Used by the resolution experiment. Entrants, exits and dormant SKUs are
    dropped rather than carried, because the question being asked is about the
    sample size of the decomposable population alone.
    """
    keep = pd.Index(skus)
    return PopulationSplit(
        totals=split.totals.loc[keep],
        decomposable=keep,
        entrants=pd.Index([]),
        exits=pd.Index([]),
        zero_actual=pd.Index([]),
    )


def emit(name: str, payload: dict, rows: list[tuple] | None = None, headers=()) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{name}.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if rows:
        widths = [
            max(len(str(header)), *(len(str(row[index])) for row in rows))
            for index, header in enumerate(headers)
        ]
        line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths, strict=True))
        print(line)
        print("-" * len(line))
        for row in rows:
            print("  ".join(str(c).ljust(w) for c, w in zip(row, widths, strict=True)))
    print(f"\nwrote {target.relative_to(OUTPUT_DIR.parents[1])}")
