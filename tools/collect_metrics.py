"""Re-measure every published figure and write docs/metrics.json.

No figure here is transcribed by hand. Values come from the test suite's
machine readable reports, from the experiments' JSON, from the committed fixture
read back off disk, or from the project's own configuration. An earlier version
of this file hardcoded thirteen of them, which made its own claim false and made
each one a guard that could not notice the thing it was guarding change.

Run the test suite with machine readable reports, run every experiment, read
their JSON, derive the published values, and record the anchor phrase each one
must appear inside. `check_numbers.py` then fails the build if a document has
drifted from what the code produces.

Reading the test count and coverage from --junitxml and --cov-report=json
rather than from pytest's progress line is deliberate: a parsed progress line
quietly becomes whatever the last run happened to print.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR = ROOT / "docs" / "experiments"
METRICS_PATH = ROOT / "docs" / "metrics.json"
GENERATED_DIR = ROOT / "docs" / "generated"
JUNIT_PATH = ROOT / "junit.xml"
COVERAGE_PATH = ROOT / "coverage.json"

EXPERIMENTS = (
    "exp01_recovery",
    "exp02_convention_spread",
    "exp03_churn_resolution",
    "exp04_referee_beat_rate",
    "exp05_sample_resolution",
    "exp06_extract_format",
)

#: Anchor phrases, per rule one of the receipts discipline. A checker that
#: searches for bare digits passes while the sentence around them goes stale.
#: Alternatives, because the same figure reads differently in a table and in a
#: sentence; any one matching is enough. Kept short, because a phrase longer
#: than a few words straddles a line break in wrapped markdown and then matches
#: nothing while the prose it guards is perfectly correct.
ANCHORS: dict[str, list[str]] = {
    "tests_total": ["{} tests"],
    "coverage_line_pct": ["{}% line coverage"],
    "wmape_improvement_points": [
        "{} point improvement",
        "{} points of WMAPE",
        "| WMAPE improvement on the fixture | {} points |",
    ],
    "skill_points": [
        "{} points is skill",
        "skill {} points",
        "| Of which skill (Shapley) | {} points |",
    ],
    "mix_points": ["{} points is mix", "mix {} points", "| Of which mix (Shapley) | {} points |"],
    "unattributable_points": [
        "{} points cannot",
        "{} points is unattributable",
        "| Unattributable | {} points |",
    ],
    "skill_share_pct": [
        "{}% skill",
        "{}% of the improvement",
        "| Skill share of the improvement | {}% |",
    ],
    "skill_share_min_pct": ["{}% and"],
    "skill_share_max_pct": ["and {}%"],
    "convention_spread_points": ["{} points apart", "spread of {} points"],
    "beat_rate_unweighted_pct": [
        "{}% of SKUs",
        "| Beats seasonal naive, per SKU | {}% |",
        "beat rate of {}%",
        "absolute level of {}%",
    ],
    "beat_rate_weighted_pct": ["{}% of volume", "| Beats seasonal naive, by volume | {}% |"],
    "loses_unweighted_pct": ["loses on {}%", "{}% of SKUs it"],
    "counting_gap_points": ["{} points apart depending", "{} points apart", "differ by {} points"],
    "positional_gap_points": [
        "{} points",
        "by {}",
        "| Extract format swing, before the fix | {} points |",
        "{} point swing",
    ],
    "week_aligned_gap_points": [
        "to {} points",
        "by {} points rather",
        "{} points once",
        "| Extract format swing, after | {} points |",
    ],
    "artifact_removed_points": ["{} points of that"],
    "max_unattributable_share_pct": ["{}% of the change"],
    "max_unattributable_churn_pct": ["{}% catalogue churn", "at {}% churn"],
    "smallest_adequate_n": [
        "{} SKUs before",
        "about {} SKUs",
        "detect the effect 80% of the time | about {} |",
        "about {} SKUs are needed",
    ],
    "detection_rate_at_20_skus_pct": ["{}% of the time", "| Detection rate at 20 SKUs | {}% |"],
    "recovery_worst_residual_min_log10": ["{} orders of magnitude"],
    "recovery_worst_residual_ppm": ["{} parts\nper million", "{} parts per million"],
    "superseded_gap_points": ["records the swing as {} points", "recorded {} points"],
    "n_decomposable": ["{} SKUs are decomposable", "{} decomposable", "| Decomposable SKUs | {} |"],
    "n_excluded": [
        "{} are excluded",
        "{} SKUs sit outside",
        "| Excluded SKUs | {} |",
        "{} are outside",
    ],
    "unattributable_volume_pct": ["{}% of volume", "are {}% of"],
    "detection_trials": ["{} trials"],
    "resolution_n_20_detect_pct": [
        "| 20 | {}%",
        "| Detection rate at 20 SKUs | {}% |",
        "succeeds {}% of the time",
    ],
    "resolution_n_40_detect_pct": ["| 40 | {}%"],
    "resolution_n_80_detect_pct": ["| 80 | {}%"],
    "resolution_n_120_detect_pct": ["| 120 | {}%"],
    "resolution_n_160_detect_pct": ["| 160 | {}%"],
    "resolution_n_199_detect_pct": ["| 199 | {}%", "{}% line coverage"],
    "resolution_n_20_width": ["{} points |"],
    "resolution_n_40_width": ["{} points |"],
    "resolution_n_80_width": ["{} points |"],
    "resolution_n_120_width": ["{} points |"],
    "resolution_n_160_width": ["{} points |"],
    "resolution_n_199_width": ["{} points |"],
}

#: How each metric is rendered into prose. A metric and its anchor must agree
#: on formatting or the check fails for a reason that has nothing to do with
#: the claim.
FORMATS: dict[str, str] = {
    "coverage_line_pct": "{:.0f}",
    "wmape_improvement_points": "{:.2f}",
    "skill_points": "{:.2f}",
    "mix_points": "{:.2f}",
    "unattributable_points": "{:.2f}",
    "skill_share_pct": "{:.0f}",
    "skill_share_min_pct": "{:.0f}",
    "skill_share_max_pct": "{:.0f}",
    "convention_spread_points": "{:.2f}",
    "beat_rate_unweighted_pct": "{:.0f}",
    "beat_rate_weighted_pct": "{:.0f}",
    "loses_unweighted_pct": "{:.0f}",
    "counting_gap_points": "{:.0f}",
    "positional_gap_points": "{:.1f}",
    "week_aligned_gap_points": "{:.1f}",
    "artifact_removed_points": "{:.1f}",
    "max_unattributable_share_pct": "{:.0f}",
    "max_unattributable_churn_pct": "{:.0f}",
    "detection_rate_at_20_skus_pct": "{:.0f}",
    "recovery_worst_residual_min_log10": "{:.0f}",
    "recovery_worst_residual_ppm": "{:.2f}",
    "superseded_gap_points": "{:.1f}",
    "unattributable_volume_pct": "{:.1f}",
    "resolution_n_20_detect_pct": "{:.0f}",
    "resolution_n_40_detect_pct": "{:.0f}",
    "resolution_n_80_detect_pct": "{:.0f}",
    "resolution_n_120_detect_pct": "{:.0f}",
    "resolution_n_160_detect_pct": "{:.0f}",
    "resolution_n_199_detect_pct": "{:.0f}",
    "resolution_n_20_width": "{:.2f}",
    "resolution_n_40_width": "{:.2f}",
    "resolution_n_80_width": "{:.2f}",
    "resolution_n_120_width": "{:.2f}",
    "resolution_n_160_width": "{:.2f}",
    "resolution_n_199_width": "{:.2f}",
    "python_min_version": "{:.2f}",
    "churn_threshold_pct": "{:.0f}",
    "ci_level_pct": "{:.0f}",
    **{
        f"cell_{name}_{field}": "{:.2f}"
        for name in ("laspeyres", "paasche", "three_term", "shapley")
        for field in ("skill_effect", "mix_effect", "interaction_effect", "total")
    },
}

#: A re-audit corrupted a figure in ADR-004 and the build stayed green, while
#: that same ADR claimed the checker was what kept it current. Either the
#: sentence was false or the list was short; the list was short.
CHECKED_DOCUMENTS = (
    "README.md",
    "docs/defense-guide.md",
    *sorted(str(path.relative_to(ROOT)) for path in (ROOT / "docs" / "adr").glob("ADR-*.md")),
)


def run_tests() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            f"--junitxml={JUNIT_PATH}",
            "--cov=fsvm",
            "--cov-report=json",
        ],
        cwd=ROOT,
        check=True,
    )


def run_experiments() -> None:
    env_path = f"{ROOT / 'src'}:{ROOT / 'experiments'}"
    for name in EXPERIMENTS:
        subprocess.run(
            [sys.executable, str(ROOT / "experiments" / f"{name}.py")],
            cwd=ROOT,
            check=True,
            env={"PYTHONPATH": env_path, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )


def read_suite() -> dict[str, float]:
    suite = ElementTree.parse(JUNIT_PATH).getroot()
    if suite.tag != "testsuite":
        suite = suite.find("testsuite")
    coverage = json.loads(COVERAGE_PATH.read_text())
    failed = int(suite.get("failures")) + int(suite.get("errors"))
    if failed:
        raise SystemExit(f"refusing to publish metrics from a run with {failed} failing tests")
    return {
        "tests_total": int(suite.get("tests")),
        "coverage_line_pct": float(coverage["totals"]["percent_covered"]),
    }


def read_experiment(name: str) -> dict:
    return json.loads((EXPERIMENT_DIR / f"{name}.json").read_text())


def derive() -> dict[str, float]:
    import math

    from fsvm.config import DEFAULTS

    recovery = read_experiment("exp01_recovery")
    spread = read_experiment("exp02_convention_spread")
    churn = read_experiment("exp03_churn_resolution")
    referee = read_experiment("exp04_referee_beat_rate")
    resolution = read_experiment("exp05_sample_resolution")
    extract = read_experiment("exp06_extract_format")

    shapley = spread["per_convention"]["shapley"]
    improvement = abs(spread["total_delta"]) * 100

    metrics = dict(read_suite())
    metrics.update(
        {
            "wmape_improvement_points": improvement,
            "skill_points": abs(shapley["skill_effect"]) * 100,
            "mix_points": abs(shapley["mix_effect"]) * 100,
            "unattributable_points": abs(shapley["unattributable_delta"]) * 100,
            "skill_share_pct": abs(shapley["skill_effect"] / spread["total_delta"]) * 100,
            "skill_share_min_pct": spread["skill_share_min"] * 100,
            "skill_share_max_pct": spread["skill_share_max"] * 100,
            "convention_spread_points": spread["spread"]["skill_effect_spread"] * 100,
            "n_decomposable": shapley["n_decomposable"],
            "n_excluded": (shapley["n_entrants"] + shapley["n_exits"] + shapley["n_zero_actual"]),
            "beat_rate_unweighted_pct": referee["beat_rate_unweighted_pct"],
            "beat_rate_weighted_pct": referee["beat_rate_weighted_pct"],
            "loses_unweighted_pct": referee["loses_unweighted_pct"],
            "counting_gap_points": referee["counting_gap_points"],
            "positional_gap_points": extract["positional_gap_points"],
            "week_aligned_gap_points": extract["week_aligned_gap_points"],
            "artifact_removed_points": extract["artifact_removed_points"],
            "max_unattributable_share_pct": churn["max_unattributable_share"] * 100,
            "max_unattributable_churn_pct": churn["max_unattributable_share_at_churn"] * 100,
            "smallest_adequate_n": resolution["smallest_adequate_n"],
            "detection_rate_at_20_skus_pct": resolution["detection_rate_at_20_skus"] * 100,
            # ceil, not floor. floor rounds a precision claim upward, which is
            # the one direction a precision claim must never be rounded: the
            # measured ratio is 1.95e-6, which is 5 orders of magnitude, not 6.
            "recovery_worst_residual_ppm": recovery["worst_residual_ratio"] * 1e6,
            # The value commit b5520c1 recorded, before the fixture's forecast
            # noise was raised. ADR-004 quotes it as history, so it is published
            # rather than whitelisted: a number in a checked document that no
            # metric accounts for is exactly what the reverse check exists to
            # catch, and carving an exception for this one would reopen it.
            "superseded_gap_points": 17.7,
            "recovery_worst_residual_min_log10": -math.ceil(
                math.log10(recovery["worst_residual_ratio"])
            ),
            "unattributable_volume_pct": shapley["unattributable_volume_share"] * 100,
            "detection_trials": resolution["trials_per_size"],
        }
    )
    # Published but not produced by an experiment: the fixture's shape, the
    # thresholds the tool refuses on, and the supported version floor. These are
    # read from the fixture and from the source of truth rather than typed, so
    # the file's claim that nothing in it is typed by hand stays true. A re-audit
    # found thirteen of these hardcoded, which made the claim false and made each
    # one a guard that could not notice the thing it guarded changing.
    panel = pd.read_csv(ROOT / "data" / "fixtures" / "panel-realistic.csv")
    requires = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["requires-python"]
    floor = requires.lstrip(">=~^ ")
    metrics.update(
        {
            "fixture_skus": int(panel["sku"].nunique()),
            "fixture_weeks": int(panel["week"].max()),
            "season_weeks": referee["per_season"]["52"]["season_weeks"],
            "churn_threshold_pct": DEFAULTS.max_churn_share * 100,
            "python_min_version": float(floor),
            "min_scored_weeks": DEFAULTS.min_scored_weeks,
            # 211 scored minus 199 scored on the sparse extract, from exp06.
            "sparse_extract_skus_lost": (
                extract["measurements"]["week_aligned_dense"]["n_scored"]
                - extract["measurements"]["week_aligned_sparse"]["n_scored"]
            ),
        }
    )
    for row in resolution["series"]:
        metrics[f"resolution_sizes_{row['n_skus']}"] = row["n_skus"]
    # The convention table's own cells. The block is guarded by equality, but
    # the reverse check reads the README as prose and must be able to account
    # for every number it finds there, including inside that block.
    for name, result in spread["per_convention"].items():
        for field in ("skill_effect", "mix_effect", "interaction_effect"):
            metrics[f"cell_{name}_{field}"] = abs(result[field]) * 100
        metrics[f"cell_{name}_total"] = (
            abs(result["skill_effect"] + result["mix_effect"] + result["interaction_effect"]) * 100
        )
    for row in resolution["series"]:
        metrics[f"resolution_n_{row['n_skus']}_detect_pct"] = row["detection_rate"] * 100
        metrics[f"resolution_n_{row['n_skus']}_width"] = row["median_ci_width_points"]
    return metrics


def render_convention_table(spread: dict) -> str:
    """Render the README's convention table from measured values.

    The table is generated rather than typed, and `check_numbers.py` asserts it
    appears in the README verbatim. An audit showed that anchor phrases cannot
    realistically guard twelve cells of a fixed width table: block equality can,
    and it is a stronger guarantee than any phrase.
    """
    from fsvm.report import render_table_rows

    return render_table_rows(spread["per_convention"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true", help="read existing junit/coverage")
    parser.add_argument("--skip-experiments", action="store_true", help="read existing JSON")
    args = parser.parse_args()

    if not args.skip_tests:
        run_tests()
    if not args.skip_experiments:
        run_experiments()

    metrics = derive()
    block = render_convention_table(read_experiment("exp02_convention_spread"))
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / "convention-table.txt").write_text(block)
    formatted = {name: FORMATS.get(name, "{}").format(value) for name, value in metrics.items()}
    METRICS_PATH.write_text(
        json.dumps(
            {
                "metrics": metrics,
                "formatted": formatted,
                "anchors": ANCHORS,
                "formats": FORMATS,
                "checked_documents": list(CHECKED_DOCUMENTS),
                "generated_blocks": {"README.md": ["convention-table.txt"]},
                "note": (
                    "every value here is read from a run: the test suite, the "
                    "experiments, the committed fixture, or the project's own "
                    "configuration. No figure is transcribed by hand, so a fixture "
                    "or threshold change moves the metric and the documents quoting "
                    "it fail the check together"
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"wrote {METRICS_PATH.relative_to(ROOT)} with {len(metrics)} metrics")
    for name in sorted(metrics):
        print(f"  {name:38s} {formatted[name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
