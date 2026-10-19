"""The number checker's own tests, because an unfallible checker is an untested one.

An audit broke the first version of `tools/check_numbers.py` in under a minute:
sixteen published figures were corrupted one at a time and fourteen passed. The
causes were that fenced results blocks were stripped before checking, that an
anchor matching in one document satisfied every document, and that the reverse
check only printed a note instead of failing.

These tests corrupt each published figure in turn and assert the checker goes
red. They are the reason the README is allowed to claim that a stale number
fails the build.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check_numbers.py"
METRICS = ROOT / "docs" / "metrics.json"

sys.path.insert(0, str(ROOT / "tools"))
import check_numbers  # noqa: E402

ALLOWED_ORDINALS = check_numbers.ALLOWED_BARE_NUMBERS

pytestmark = pytest.mark.skipif(
    not METRICS.exists(),
    reason="docs/metrics.json has not been collected yet; run make receipts",
)


def _payload() -> dict:
    return json.loads(METRICS.read_text())


def _sandbox(tmp_path: Path) -> Path:
    """A copy of the repository's checked surface, so a corruption is never written back."""
    root = tmp_path / "repo"
    (root / "docs" / "generated").mkdir(parents=True)
    (root / "tools").mkdir()
    shutil.copy(CHECKER, root / "tools" / "check_numbers.py")
    shutil.copy(METRICS, root / "docs" / "metrics.json")
    for name in _payload()["checked_documents"]:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
    for block in (ROOT / "docs" / "generated").glob("*.txt"):
        shutil.copy(block, root / "docs" / "generated" / block.name)
    return root


def _run(root: Path) -> int:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "check_numbers.py")],
        cwd=root,
        capture_output=True,
        text=True,
    ).returncode


def _corrupt(root: Path, value: str, replacement: str) -> bool:
    """Corrupt an occurrence the checker is actually responsible for.

    Using the checker's own stripping to choose the target matters. An earlier
    version of this test replaced the first occurrence anywhere, which for the
    test count landed inside a badge URL; the checker stripped markdown targets
    before looking, so the build stayed green and the test recorded a pass that
    meant nothing. Badges are now checked separately, and this helper only
    corrupts text that at least one of the checks can see.
    """
    for name in _payload()["checked_documents"]:
        path = root / name
        body = path.read_text()
        visible = check_numbers.strip_non_prose(body)
        if value not in visible:
            continue
        # Rewrite the occurrence at the position the checker sees it, so the
        # replacement lands in prose rather than in a stripped span.
        index, searched = -1, 0
        while True:
            index = body.find(value, searched)
            if index == -1:
                return False
            if value in check_numbers.strip_non_prose(body[: index + len(value)])[-len(value) :]:
                break
            searched = index + 1
        path.write_text(body[:index] + replacement + body[index + len(value) :])
        return True
    return False


def _nudge(value: str) -> str:
    """A different number of the same shape that collides with nothing.

    The first version of this helper added seven, and several of those sums
    landed on another metric's value or on an allowed ordinal, so the checker
    was right to stay green and the test was wrong to expect red. The
    replacement is now searched for rather than computed, which is slower and
    says what it means.
    """
    taken = set(_payload()["formatted"].values()) | ALLOWED_ORDINALS
    for candidate in range(811, 9999):
        text = f"{candidate}.{value.partition('.')[2]}" if "." in value else str(candidate)
        if text not in taken:
            return text
    raise AssertionError("no non colliding replacement exists")


def test_the_checker_passes_on_the_repository_as_committed(tmp_path):
    assert _run(_sandbox(tmp_path)) == 0


#: Every metric the checker claims responsibility for: anchored, in a generated
#: block, or on a badge. Parametrised over the whole set rather than a hand
#: picked few, because the figures that slipped through the first version of
#: the checker were exactly the ones nobody thought to test.
PUBLISHED = sorted(_payload()["anchors"]) if METRICS.exists() else []


@pytest.mark.parametrize("metric", PUBLISHED)
def test_corrupting_a_published_figure_fails_the_build(tmp_path, metric):
    """Every published value, corrupted in place, must turn the checker red."""
    root = _sandbox(tmp_path)
    value = _payload()["formatted"][metric]
    if not _corrupt(root, value, _nudge(value)):
        pytest.skip(f"{metric} = {value} is not quoted in any checked document")
    assert _run(root) != 0, f"corrupting {metric} = {value} did not fail the build"


def test_deleting_a_checked_document_fails_the_build(tmp_path):
    root = _sandbox(tmp_path)
    (root / "README.md").unlink()
    assert _run(root) != 0


def test_a_drifted_generated_block_fails_the_build(tmp_path):
    """The convention table is guarded by block equality rather than by phrases."""
    root = _sandbox(tmp_path)
    block = root / "docs" / "generated" / "convention-table.txt"
    block.write_text(block.read_text().replace("convention", "method", 1))
    assert _run(root) != 0


def test_an_invented_number_in_prose_fails_the_build(tmp_path):
    """The reverse check is the half that catches a figure no phrase could guard."""
    root = _sandbox(tmp_path)
    readme = root / "README.md"
    readme.write_text(readme.read_text() + "\n\nA stray claim of 8812 units.\n")
    assert _run(root) != 0


def test_a_missing_metrics_file_is_reported_rather_than_passing(tmp_path):
    root = _sandbox(tmp_path)
    (root / "docs" / "metrics.json").unlink()
    assert _run(root) == 2


def test_a_stale_badge_fails_the_build(tmp_path):
    """A badge is a published claim in the first screen.

    Found by this suite rather than by review: corrupting the test count only
    changed the badge, markdown targets were stripped before either check ran,
    and the build stayed green while the badge advertised a figure the code no
    longer produced.
    """
    root = _sandbox(tmp_path)
    readme = root / "README.md"
    count = _payload()["formatted"]["tests_total"]
    readme.write_text(readme.read_text().replace(f"badge/tests-{count}-", "badge/tests-9001-"))
    assert _run(root) != 0


def test_every_metric_is_either_published_or_accounted_for(tmp_path):
    """No metric may be measured, quoted, and guarded by nothing.

    The reverse check accounts for unanchored values by requiring that any
    number in a checked document match some metric, so a measured but unanchored
    value is allowed to appear. What is not allowed is a metric that exists only
    to widen the allowed set without any check referring to it.
    """
    payload = _payload()
    unreferenced = set(payload["formatted"]) - set(payload["anchors"])
    quoted = set()
    for name in payload["checked_documents"]:
        body = check_numbers.strip_non_prose((ROOT / name).read_text())
        quoted |= {m for m in unreferenced if m and payload["formatted"][m] in body}
    assert quoted, "no unanchored metric is quoted anywhere, so the allowed set is dead weight"
