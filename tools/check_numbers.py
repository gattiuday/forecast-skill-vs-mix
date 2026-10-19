"""Fail the build when a document quotes a figure the code no longer produces.

This file was rewritten after an audit demonstrated that its first version did
not do what the README claimed it did. Sixteen published figures were corrupted
one at a time; fourteen passed. The three causes, and what replaced them:

1. **Fenced blocks were stripped wholesale.** The convention table, which is the
   centrepiece of the README, lives in a fence, so seven published values had no
   guard at all. Now only fences tagged as commands (```bash) are stripped,
   because an example invocation may legitimately contain an invented row count.
   A results block is prose with a monospace font and is checked like prose.

2. **An anchor matching in one document satisfied every document.** The defense
   guide quotes the same figures and was therefore almost entirely unguarded.
   Now every checked document is checked on its own.

3. **The reverse check only printed a note.** That was the real hole. A forward
   check can only confirm that a correct sentence exists somewhere; it cannot
   notice a corrupted one. Corrupting 2.86 to 9.99 leaves the anchored sentence
   absent *and* introduces a number matching no metric, and it is the second of
   those that catches a figure quoted in a table cell or a prose aside. The
   reverse check now fails the build, and the allowed list is small enough that
   it means something.

Anchors are still alternatives within a document, because the same figure reads
differently in a table and in a sentence, and requiring all of them would fail
the build for prose that is perfectly correct.

`tests/test_check_numbers.py` corrupts every published figure in turn and
asserts this script exits non zero. A checker nobody has watched fail is a
checker nobody should believe.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "docs" / "metrics.json"

#: Only command fences are stripped. A bare fence holds results and is checked.
COMMAND_FENCE = re.compile(r"```(?:bash|sh|console|python)\n.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HTML_ATTRIBUTE = re.compile(r'\w+="[^"]*"')
MARKDOWN_TARGET = re.compile(r"\]\([^)]*\)")
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
#: shields.io badge values. A badge is a published claim sitting in the first
#: screen, and stripping markdown targets hid it from both checks. The test
#: suite found that: corrupting the test count only changed the badge, and the
#: build stayed green.
BADGE = re.compile(r"img\.shields\.io/badge/(?P<label>[^-\s]+)-(?P<value>[^-\s]+)-")
BADGE_RANGE = re.compile(r"img\.shields\.io/badge/(?P<label>[a-z]+)-(?P<value>[\d.%A-F]+)-")

#: Numbers that appear for reasons unrelated to a measurement. Deliberately
#: short: every entry here is a figure the reverse check can no longer catch,
#: so each one is a hole that has to earn its place. Values that look like
#: results (the fixture's shape, the supported Python versions) are declared as
#: metrics in collect_metrics.py instead of being whitelisted here.
ALLOWED_BARE_NUMBERS = {
    # small ordinals and counts used structurally in prose
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    # ADR file numbers as they appear in link text and cross references
    "001",
    "002",
    "003",
    "004",
    "005",
}


def strip_non_prose(text: str) -> str:
    """Remove the parts of a document that may legitimately contain invented numbers."""
    text = COMMAND_FENCE.sub(" ", text)
    text = INLINE_CODE.sub(" ", text)
    text = MARKDOWN_TARGET.sub(" ", text)
    return HTML_ATTRIBUTE.sub(" ", text)


def flatten(text: str) -> str:
    """Collapse every run of whitespace, newlines included.

    An anchor phrase that spans a line break in wrapped markdown matched nothing
    while the prose it guarded was correct. Collapsing only horizontal space was
    not enough: a re-audit found "about 160 SKUs" failing against a document
    that said exactly that, with a newline between the number and the noun.
    """
    return re.sub(r"\s+", " ", text)


def normalise(text: str) -> str:
    """Collapse whitespace so an anchor still matches across a wrapped line.

    An anchor phrase that spans a newline in wrapped markdown matches nothing
    while the prose it guards is correct, so anchors are matched against a
    single spaced version of the document.
    """
    return re.sub(r"[^\S\n]+", " ", text)


def load_documents(payload: dict) -> dict[str, str] | None:
    documents = {}
    for name in payload["checked_documents"]:
        path = ROOT / name
        if not path.exists():
            print(f"FAIL  checked document is missing: {name}", file=sys.stderr)
            return None
        documents[name] = normalise(strip_non_prose(path.read_text()))
    return documents


def forward_check(payload: dict, documents: dict[str, str]) -> tuple[list[str], list[str]]:
    """Every anchored metric must appear, inside an anchor phrase, where it is claimed.

    A metric is required in a document only if that document mentions its value
    at all. That keeps the README's exclusive figures from being demanded of the
    defense guide, while still checking any figure the defense guide does quote.
    """
    formatted, anchors = payload["formatted"], payload["anchors"]
    verified, failures = [], []
    #: Values shared by more than one metric. Demanding every colliding metric's
    #: anchor turns a correct sentence into a failure: the README says "41% skill"
    #: for the skill share, and the excluded SKU count is also 41. One matching
    #: anchor for the value is enough, and which metric it belongs to is a
    #: question the document's wording already answers.
    satisfied: dict[tuple[str, str], bool] = {}
    for metric in sorted(anchors):
        phrases = anchors[metric]
        value = formatted.get(metric)
        if value is None:
            failures.append(f"{metric}: anchored but never measured")
            continue
        if not phrases:
            failures.append(f"{metric}: has no anchor phrase, so nothing re-checks the prose")
            continue
        candidates = [flatten(phrase.format(value)) for phrase in phrases]
        for name, body in documents.items():
            if any(candidate in flatten(body) for candidate in candidates):
                satisfied[(name, value)] = True
                verified.append(f"OK    {metric} = {value}  ({name})")
            elif value in NUMBER.findall(body):
                failures.append(
                    (
                        name,
                        value,
                        f"{metric} = {value} appears in {name} but not inside any anchor: "
                        + " | ".join(repr(c) for c in candidates),
                    )
                )
    return verified, [
        message for name, value, message in failures if not satisfied.get((name, value), False)
    ]


def reverse_check(payload: dict, documents: dict[str, str]) -> list[str]:
    """Every number in a checked document must be a measured value or an allowed ordinal.

    This is the half that catches a corrupted figure. A forward check confirms
    that a correct sentence exists; only this one notices that a wrong number
    was introduced.
    """
    known = set(payload["formatted"].values())
    failures = []
    for name, body in documents.items():
        for line_number, line in enumerate(body.split("\n"), start=1):
            for found in NUMBER.findall(line):
                if found in ALLOWED_BARE_NUMBERS or found in known:
                    continue
                failures.append(
                    f"{name}:{line_number}: {found} matches no measured metric and is not "
                    "an allowed ordinal"
                )
    return failures


#: Which badge label must equal which metric.
BADGE_METRICS = {"tests": "tests_total", "coverage": "coverage_line_pct"}

#: Badges whose value is a list rather than a single figure. The python badge
#: advertises the supported versions and was checked against neither
#: pyproject's floor nor the CI matrix; the argument for checking the other two
#: applies to it unchanged.
BADGE_RANGES = {"python": "python_min_version"}


def badge_check(payload: dict) -> list[str]:
    """Badge values are published claims and must match the measured metric."""
    formatted = payload["formatted"]
    failures = []
    for name in payload["checked_documents"]:
        for match in BADGE.finditer((ROOT / name).read_text()):
            label = match.group("label")
            metric = BADGE_METRICS.get(label)
            if metric is None:
                continue
            expected = formatted[metric]
            actual = match.group("value").replace("%25", "").replace("%20", " ")
            if actual != expected:
                failures.append(
                    f"{name}: the {label} badge reads {actual} but {metric} measures {expected}"
                )
        for match in BADGE_RANGE.finditer((ROOT / name).read_text()):
            metric = BADGE_RANGES.get(match.group("label"))
            if metric is None:
                continue
            listed = match.group("value").replace("%20", " ").replace("%7C", "|")
            floor = formatted[metric]
            if not listed.strip().startswith(floor):
                failures.append(
                    f"{name}: the {match.group('label')} badge lists '{listed}' but the "
                    f"project's own floor is {floor}"
                )
    return failures


def block_check(payload: dict) -> list[str]:
    """Generated blocks must appear in their document verbatim.

    Twelve cells of a fixed width table cannot realistically be guarded by
    anchor phrases. Block equality guards all of them at once, and it is a
    stronger guarantee than any phrase: the document either contains exactly
    what the code produced, or it does not.
    """
    failures = []
    for name, blocks in payload.get("generated_blocks", {}).items():
        document = (ROOT / name).read_text()
        for block_name in blocks:
            source = ROOT / "docs" / "generated" / block_name
            if not source.exists():
                failures.append(f"{name}: generated block {block_name} has not been written")
                continue
            if source.read_text().rstrip("\n") not in document:
                failures.append(
                    f"{name}: does not contain docs/generated/{block_name} verbatim; "
                    "the document has drifted from what the code produced"
                )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=None, help="also write a markdown summary")
    parser.add_argument(
        "--metrics", type=Path, default=METRICS_PATH, help="metrics file to check against"
    )
    args = parser.parse_args()

    if not args.metrics.exists():
        print(f"{args.metrics} is missing; run tools/collect_metrics.py first", file=sys.stderr)
        return 2
    payload = json.loads(args.metrics.read_text())

    documents = load_documents(payload)
    if documents is None:
        return 1

    verified, stale = forward_check(payload, documents)
    unverified = reverse_check(payload, documents)
    drifted = block_check(payload) + badge_check(payload)

    for line in verified:
        print(line)
    for failure in stale:
        print(f"FAIL  {failure}", file=sys.stderr)
    for failure in unverified:
        print(f"FAIL  {failure}", file=sys.stderr)
    for failure in drifted:
        print(f"FAIL  {failure}", file=sys.stderr)

    total = len(stale) + len(unverified) + len(drifted)
    print(
        f"\n{len(verified)} anchored figures verified across "
        f"{len(documents)} documents, {len(stale)} stale, "
        f"{len(unverified)} numbers matching no metric, "
        f"{len(drifted)} generated blocks drifted"
    )

    if args.summary:
        args.summary.write_text(
            "## Receipts\n\n"
            f"- {len(verified)} anchored figures verified across {len(documents)} documents\n"
            f"- {len(stale)} figures quoted outside their anchor phrase\n"
            f"- {len(unverified)} numbers in prose matching no measured metric\n\n"
            + f"- {len(drifted)} generated blocks that have drifted\n\n"
            + ("\n".join(f"- FAIL {f}" for f in stale + unverified + drifted) if total else "")
            + "\n"
        )
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
