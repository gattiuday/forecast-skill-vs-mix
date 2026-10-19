"""Command line entry point, with exit codes that distinguish "no" from "cannot say".

    0  the improvement was attributed to forecasting skill
    1  the analysis ran and the answer was no: mix dominated, the interval
       covered zero, or too much volume was unattributable
    2  the analysis could not be run: the panel does not support an attribution
    3  usage error

Codes 1 and 2 are kept apart because a planning team wiring this into a monthly
review needs to page someone for 2 and read the report for 1. A single non zero
code would make that impossible without parsing stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fsvm.baseline import DEFAULT_SEASON_WEEKS, beat_rate
from fsvm.config import CONVENTIONS, DEFAULT_CONVENTION, DEFAULTS
from fsvm.decompose import convention_spread, decompose_all_conventions
from fsvm.errors import AttributionError
from fsvm.generator import SCENARIOS, generate_panel
from fsvm.panel import load_panel, split_populations, to_period_totals
from fsvm.report import judge, render_table
from fsvm.resample import skill_effect_interval

EXIT_OK = 0
EXIT_NOT_ATTRIBUTED = 1
EXIT_CANNOT_ANSWER = 2
EXIT_USAGE = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fsvm",
        description=(
            "Attribute a change in portfolio forecast accuracy between forecasting "
            "skill and SKU mix shift."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a seeded demand panel to CSV")
    gen.add_argument("--out", required=True, type=Path)
    gen.add_argument("--scenario", default="realistic", choices=SCENARIOS)
    gen.add_argument("--skus", type=int, default=240)
    gen.add_argument("--weeks", type=int, default=104)
    gen.add_argument("--split-week", type=int, default=53)
    gen.add_argument("--seed", type=int, default=20260419)

    att = sub.add_parser("attribute", help="decompose a WMAPE change into skill and mix")
    att.add_argument("--panel", required=True, type=Path)
    att.add_argument("--split-week", type=int, default=53)
    att.add_argument("--convention", default=DEFAULT_CONVENTION, choices=CONVENTIONS)
    att.add_argument("--bootstrap", type=int, default=DEFAULTS.bootstrap_samples)
    att.add_argument("--json", type=Path, default=None, help="also write the full result here")

    ref = sub.add_parser("referee", help="score the forecast against a seasonal naive baseline")
    ref.add_argument("--panel", required=True, type=Path)
    ref.add_argument("--split-week", type=int, default=53)
    ref.add_argument("--season", type=int, default=DEFAULT_SEASON_WEEKS)
    return parser


def _run_generate(args: argparse.Namespace) -> int:
    panel = generate_panel(
        n_skus=args.skus,
        weeks=args.weeks,
        split_week=args.split_week,
        scenario=args.scenario,
        seed=args.seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out, index=False)
    print(f"wrote {len(panel)} rows for {panel['sku'].nunique()} SKUs to {args.out}")
    return EXIT_OK


def _run_attribute(args: argparse.Namespace) -> int:
    panel = load_panel(args.panel)
    split = split_populations(to_period_totals(panel, args.split_week))
    results = decompose_all_conventions(split)
    spread = convention_spread(results)
    chosen = results[args.convention]
    interval = skill_effect_interval(split, args.convention, samples=args.bootstrap)
    verdict = judge(chosen, interval)

    print(render_table(results, spread))
    print()
    print(f"Reported convention: {args.convention}")
    print(
        f"{interval['ci_level']:.0%} bootstrap interval on the skill effect: "
        f"[{interval['skill_effect_ci_low'] * 100:+.2f}, "
        f"{interval['skill_effect_ci_high'] * 100:+.2f}] points"
    )
    print()
    print(f"VERDICT: {verdict.status}")
    for reason in verdict.reasons:
        print(f"  - {reason}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "conventions": {name: r.as_dict() for name, r in results.items()},
                    "spread": spread,
                    "interval": interval,
                    "verdict": {"status": verdict.status, "reasons": list(verdict.reasons)},
                },
                indent=2,
            )
            + "\n"
        )
    return verdict.exit_code


def _run_referee(args: argparse.Namespace) -> int:
    panel = load_panel(args.panel)
    scores = beat_rate(panel, args.split_week, args.season)
    print(f"Scored {scores['n_scored']} SKUs against a {scores['season_weeks']} week naive referee")
    print(f"  undefined (too little history or an exact referee): {scores['n_undefined']}")
    print(f"  beats the referee, unweighted:      {scores['beat_rate_unweighted']:.1%} of SKUs")
    print(f"  beats the referee, volume weighted: {scores['beat_rate_volume_weighted']:.1%}")
    print(f"  median MASE: {scores['median_mase']:.3f}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage; remap so 2 stays meaningful
        return EXIT_USAGE if exc.code else EXIT_OK

    handlers = {
        "generate": _run_generate,
        "attribute": _run_attribute,
        "referee": _run_referee,
    }
    try:
        return handlers[args.command](args)
    except AttributionError as exc:
        # Includes UndefinedMetric, which is also a ValueError. Order matters:
        # this clause must come first so a domain refusal is reported as
        # "cannot answer" rather than as a usage error. Pinned by
        # test_an_undefined_metric_is_a_cannot_answer_not_a_usage_error.
        print(f"cannot answer: {exc}", file=sys.stderr)
        return EXIT_CANNOT_ANSWER
    except (ValueError, OSError) as exc:
        # A bad flag value or a path the filesystem refuses. The caller named
        # the wrong thing, so it is 3 rather than 2.
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
