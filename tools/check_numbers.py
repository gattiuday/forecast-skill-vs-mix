"""Fail the build when a document quotes a figure the code no longer produces.

Two directions:

Forward
    Every metric that carries an anchor phrase must appear, inside that phrase,
    in at least one checked document. Anchors are alternatives: the same figure
    reads differently in a table and in a sentence, and requiring all of them
    would fail the build for prose that is perfectly correct, which is the
    fastest way to teach somebody to pass --no-verify.

Reverse
    Every number in a checked document should correspond to some metric.
    Reported rather than enforced, because prose legitimately contains version
    numbers, years and ordinals. Fenced code, inline code spans and HTML
    attributes are excluded: an example invocation is allowed to contain an
    invented row count, and flagging it trains the reader to skip the section.

The checker matches phrases rather than digits because a digit search passes
while the sentence around it has gone stale: "10 SKUs" is still found in a
document that now says "10 weeks".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "docs" / "metrics.json"

FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HTML_ATTRIBUTE = re.compile(r'\w+="[^"]*"')
#: Markdown link and image targets. A badge URL carries a percent encoded "%25"
#: and a shields.io path segment, neither of which is a claim about anything.
MARKDOWN_TARGET = re.compile(r"\]\([^)]*\)")
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")

#: Numbers that appear in prose for reasons unrelated to a measurement.
ALLOWED_BARE_NUMBERS = {
    # ordinals, counts and structural references that are not measurements
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "8",
    "10",
    "11",
    "12",
    # ADR file numbers, as they appear in link text
    "001",
    "002",
    "003",
    "004",
    "005",
    # fixture shape and supported versions, declared rather than measured
    "52",
    "26",
    "104",
    "240",
    "53",
    "20",
    "40",
    "80",
    "120",
    "160",
    "199",
    "3.11",
    "3.12",
    "3.13",
    "203.12",
    "203.13",
    "2026",
    "100",
    # thresholds from config.py, which are judgement calls rather than results
    "35",
    "90",
    "2000",
}


def strip_code(text: str) -> str:
    text = FENCE.sub(" ", text)
    text = INLINE_CODE.sub(" ", text)
    text = MARKDOWN_TARGET.sub(" ", text)
    return HTML_ATTRIBUTE.sub(" ", text)


def normalise(text: str) -> str:
    """Collapse whitespace so an anchor still matches across a wrapped line.

    Rule two of the receipts discipline, learned the hard way: an anchor phrase
    that spans a newline in wrapped markdown matches nothing, while the prose it
    was guarding is correct.
    """
    return re.sub(r"\s+", " ", text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=None, help="also write a markdown summary")
    args = parser.parse_args()

    if not METRICS_PATH.exists():
        print("docs/metrics.json is missing; run tools/collect_metrics.py first", file=sys.stderr)
        return 2
    payload = json.loads(METRICS_PATH.read_text())
    formatted = payload["formatted"]
    anchors = payload["anchors"]

    documents = {}
    for name in payload["checked_documents"]:
        path = ROOT / name
        if not path.exists():
            print(f"FAIL  checked document is missing: {name}", file=sys.stderr)
            return 1
        documents[name] = normalise(strip_code(path.read_text()))

    failures: list[str] = []
    gaps: list[str] = []
    matched_values: set[str] = set()
    lines: list[str] = []

    for metric in sorted(anchors):
        phrases = anchors[metric]
        value = formatted.get(metric)
        if value is None:
            failures.append(f"{metric}: anchored but never measured")
            continue
        if not phrases:
            gaps.append(f"{metric} = {value} has no anchor, so nothing re-checks the prose")
            continue
        candidates = [phrase.format(value) for phrase in phrases]
        where = [name for name, body in documents.items() if any(c in body for c in candidates)]
        if where:
            matched_values.add(value)
            lines.append(f"OK    {metric} = {value}  ({', '.join(where)})")
        else:
            failures.append(
                f"{metric} = {value} appears in no checked document as any of: "
                + " | ".join(repr(c) for c in candidates)
            )

    unverified: list[str] = []
    for name, body in documents.items():
        for found in sorted(set(NUMBER.findall(body))):
            if found in ALLOWED_BARE_NUMBERS or found in matched_values:
                continue
            if found in set(formatted.values()):
                continue
            unverified.append(f"{name}: {found} matches no metric")

    for line in lines:
        print(line)
    for gap in gaps:
        print(f"GAP   {gap}")
    for item in unverified:
        print(f"NOTE  {item}")
    for failure in failures:
        print(f"FAIL  {failure}", file=sys.stderr)

    print(
        f"\n{len(lines)} anchored figures verified, {len(gaps)} without an anchor, "
        f"{len(unverified)} numbers in prose matching no metric, {len(failures)} stale"
    )

    if args.summary:
        args.summary.write_text(
            "## Receipts\n\n"
            f"- {len(lines)} anchored figures verified against measured values\n"
            f"- {len(gaps)} metrics carry no anchor phrase\n"
            f"- {len(unverified)} numbers in prose match no metric\n"
            f"- {len(failures)} stale figures\n\n"
            + ("\n".join(f"- FAIL {failure}" for failure in failures) if failures else "")
            + "\n"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
