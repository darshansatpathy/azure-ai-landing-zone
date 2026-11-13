from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tfpolicy import __version__, report
from tfpolicy.cli import main
from tfpolicy.engine import Report

Scan = Callable[..., Report]
BAD = (
    'resource "azurerm_cognitive_account" "a" {\n  public_network_access_enabled = true\n}\n\n'
    '# tfpolicy:ignore TFP008 reason="because"\nresource "azurerm_key_vault" "k" {\n  name = "k"\n}\n'
)


def test_text_report_counts(scan: Scan) -> None:
    text = report.to_text(scan(BAD), "high")
    assert "CRITICAL TFP001" in text and "suppressed TFP008 (because)" in text
    assert text.strip().splitlines()[-1].startswith("1 modules, ")


def test_json_report_round_trips(scan: Scan) -> None:
    data = json.loads(report.to_json(scan(BAD), "medium"))
    assert data["tool"] == "tfpolicy" and data["version"] == __version__
    assert any(f["rule"] == "TFP001" and not f["suppressed"] for f in data["findings"])
    assert any(f["rule"] == "TFP008" and f["suppressed"] for f in data["findings"])


def test_markdown_report_sections(scan: Scan) -> None:
    md = report.to_markdown(scan(BAD), "medium")
    assert "| critical | 1 |" in md and "## Findings" in md and "## Suppressions" in md
    clean = report.to_markdown(
        scan('variable "a" {\n  type        = string\n  description = "d"\n}\n'), "medium"
    )
    assert "## Findings" not in clean
    from tfpolicy.engine import Config

    disabled = report.to_markdown(
        scan(BAD, cfg=Config(disabled={"TFP015": "policy applies tags"})), "medium"
    )
    assert "## Disabled rules" in disabled and "policy applies tags" in disabled


def test_sarif_is_valid_and_marks_suppressions(scan: Scan) -> None:
    doc = json.loads(report.to_sarif(scan(BAD), "medium"))
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert len(run["tool"]["driver"]["rules"]) == 24
    results = run["results"]
    assert any(r["ruleId"] == "TFP001" and r["level"] == "error" for r in results)
    suppressed = [r for r in results if r.get("suppressions")]
    assert suppressed and suppressed[0]["suppressions"][0]["justification"] == "because"
    for r in results:
        assert r["locations"][0]["physicalLocation"]["region"]["startLine"] >= 1


def test_rules_markdown_lists_every_rule() -> None:
    md = report.rules_markdown()
    for n in range(1, 25):
        assert f"## TFP{n:03d}:" in md


def test_cli_check_exit_codes_and_formats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "main.tf").write_text(BAD, encoding="utf-8")
    assert main(["check", str(tmp_path), "--config", str(tmp_path / "none.toml")]) == 1
    assert "TFP001" in capsys.readouterr().out
    assert (
        main(
            [
                "check",
                str(tmp_path),
                "--config",
                str(tmp_path / "none.toml"),
                "--fail-on",
                "critical",
            ]
        )
        == 1
    )
    (tmp_path / "main.tf").write_text(
        'variable "a" {\n  type        = string\n  description = "d"\n}\n', encoding="utf-8"
    )
    assert (
        main(
            [
                "check",
                str(tmp_path),
                "--fail-on",
                "critical",
                "--config",
                str(tmp_path / "none.toml"),
            ]
        )
        == 0
    )
    for fmt in ("json", "markdown", "sarif"):
        assert (
            main(
                [
                    "check",
                    str(tmp_path),
                    "--format",
                    fmt,
                    "--config",
                    str(tmp_path / "none.toml"),
                    "--fail-on",
                    "critical",
                ]
            )
            == 0
        )
    assert capsys.readouterr().out


def test_cli_writes_report_file_and_uses_config_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    infra = tmp_path / "infra"
    infra.mkdir()
    (infra / "main.tf").write_text(BAD, encoding="utf-8")
    cfg = tmp_path / "tfpolicy.toml"
    cfg.write_text('[tfpolicy]\npaths = ["infra"]\nfail_on = "critical"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "r.sarif"
    assert main(["check", "--config", str(cfg), "--format", "sarif", "--output", str(out)]) == 1
    assert json.loads(out.read_text(encoding="utf-8"))["version"] == "2.1.0"
    assert "TFP001" in capsys.readouterr().out


def test_cli_missing_path_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", str(tmp_path / "nope"), "--config", str(tmp_path / "c.toml")]) == 2
    assert "path not found" in capsys.readouterr().err


def test_cli_fmt_check_and_rules(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "a.tf"
    f.write_text('r "t" "n" {\n  a = 1\n  bbb = 2\n}\n', encoding="utf-8")
    assert main(["fmt-check", str(f)]) == 1
    assert "aligned" in capsys.readouterr().out
    f.write_text('r "t" "n" {\n  a   = 1\n  bbb = 2\n}\n', encoding="utf-8")
    assert main(["fmt-check", str(f)]) == 0
    assert main(["rules"]) == 0
    assert "TFP001" in capsys.readouterr().out
    assert main(["rules", "--format", "markdown"]) == 0
    assert capsys.readouterr().out.startswith("# Policy rules")


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0 and __version__ in capsys.readouterr().out
