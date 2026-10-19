"""Exit codes, because the distinction between "no" and "cannot say" is the contract."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from fsvm.cli import (
    EXIT_CANNOT_ANSWER,
    EXIT_NOT_ATTRIBUTED,
    EXIT_OK,
    EXIT_USAGE,
    main,
)


def test_generate_writes_a_panel_and_exits_zero(tmp_path, capsys):
    out = tmp_path / "p.csv"
    assert main(["generate", "--out", str(out), "--skus", "40"]) == EXIT_OK
    assert out.exists()
    assert "40 SKUs" in capsys.readouterr().out


def test_generate_creates_missing_parent_directories(tmp_path):
    out = tmp_path / "nested" / "deeper" / "p.csv"
    assert main(["generate", "--out", str(out), "--skus", "40"]) == EXIT_OK
    assert out.exists()


@pytest.mark.parametrize("scenario", ["pure_mix", "pure_skill", "realistic"])
def test_generate_accepts_every_scenario(tmp_path, scenario):
    out = tmp_path / f"{scenario}.csv"
    assert main(["generate", "--out", str(out), "--skus", "40", "--scenario", scenario]) == EXIT_OK


def test_attribute_on_the_project_fixture_exits_zero(fixture_csv):
    assert main(["attribute", "--panel", str(fixture_csv), "--bootstrap", "300"]) == EXIT_OK


def test_attribute_prints_the_convention_table_and_a_verdict(fixture_csv, capsys):
    main(["attribute", "--panel", str(fixture_csv), "--bootstrap", "300"])
    out = capsys.readouterr().out
    assert "convention" in out
    assert "VERDICT:" in out
    assert "Unattributable change" in out


def test_attribute_writes_a_json_result_when_asked(tmp_path, fixture_csv):
    target = tmp_path / "out" / "result.json"
    main(["attribute", "--panel", str(fixture_csv), "--bootstrap", "300", "--json", str(target)])
    payload = json.loads(target.read_text())
    assert set(payload) == {"conventions", "spread", "interval", "verdict"}
    assert len(payload["conventions"]) == 4


def test_attribute_returns_one_when_the_answer_is_no(tmp_path, realistic_panel):
    """A panel whose forecast got worse per SKU must exit 1, not 0 and not 2."""
    worsened = realistic_panel.copy()
    late = worsened["week"] >= 53
    worsened.loc[late, "forecast"] = worsened.loc[late, "actual"] * 2.5
    path = tmp_path / "worse.csv"
    worsened.to_csv(path, index=False)
    assert main(["attribute", "--panel", str(path), "--bootstrap", "300"]) == EXIT_NOT_ATTRIBUTED


def test_attribute_returns_two_when_the_panel_cannot_support_an_attribution(tmp_path, capsys):
    frame = pd.DataFrame(
        {"sku": ["A", "A"], "week": [1, 2], "actual": [1.0, 1.0], "forecast": [1.0, 1.0]}
    )
    path = tmp_path / "thin.csv"
    frame.to_csv(path, index=False)
    assert main(["attribute", "--panel", str(path), "--split-week", "2"]) == EXIT_CANNOT_ANSWER
    assert "cannot answer:" in capsys.readouterr().err


def test_attribute_returns_two_rather_than_three_for_a_malformed_panel(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"sku": ["A"], "week": [1]}).to_csv(path, index=False)
    assert main(["attribute", "--panel", str(path)]) == EXIT_CANNOT_ANSWER


def test_attribute_returns_three_for_a_missing_file(tmp_path, capsys):
    assert main(["attribute", "--panel", str(tmp_path / "nope.csv")]) == EXIT_USAGE
    assert "usage error:" in capsys.readouterr().err


def test_an_unknown_convention_is_rejected_as_a_usage_error(fixture_csv):
    assert main(["attribute", "--panel", str(fixture_csv), "--convention", "oaxaca"]) == EXIT_USAGE


def test_an_unknown_subcommand_is_a_usage_error():
    assert main(["decompose-everything"]) == EXIT_USAGE


def test_no_subcommand_is_a_usage_error():
    assert main([]) == EXIT_USAGE


def test_help_exits_cleanly():
    assert main(["--help"]) == EXIT_OK


def test_referee_scores_the_fixture_and_exits_zero(fixture_csv, capsys):
    assert main(["referee", "--panel", str(fixture_csv)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "beats the referee, unweighted" in out
    assert "median MASE" in out


def test_referee_returns_two_when_no_sku_has_enough_history(tmp_path, realistic_panel):
    short = realistic_panel[realistic_panel["week"] <= 54]
    path = tmp_path / "short.csv"
    short.to_csv(path, index=False)
    assert main(["referee", "--panel", str(path), "--season", "52"]) == EXIT_CANNOT_ANSWER


def test_every_exit_code_has_a_distinct_value():
    codes = {EXIT_OK, EXIT_NOT_ATTRIBUTED, EXIT_CANNOT_ANSWER, EXIT_USAGE}
    assert codes == {0, 1, 2, 3}
