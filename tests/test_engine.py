from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tfpolicy.engine import Config, Report, discover_modules, load_module, severity_rank

from .conftest import ids

Scan = Callable[..., Report]

KV = 'resource "azurerm_key_vault" "k" {\n  name = "k"\n}\n'


def test_suppression_with_reason_hides_finding_and_records_it(scan: Scan) -> None:
    text = '# tfpolicy:ignore TFP008 reason="reached over the firewall"\n' + KV
    report = scan(text)
    assert "TFP008" not in ids(report)
    sup = [f for f in report.suppressed if f.rule_id == "TFP008"]
    assert sup and sup[0].reason == "reached over the firewall"


def test_suppression_on_the_same_line_as_the_block(scan: Scan) -> None:
    text = (
        'resource "azurerm_key_vault" "k" { # tfpolicy:ignore TFP008 reason="x"\n  name = "k"\n}\n'
    )
    assert "TFP008" not in ids(scan(text))


def test_suppression_without_reason_does_not_suppress(scan: Scan) -> None:
    report = scan("# tfpolicy:ignore TFP008\n" + KV)
    assert {"TFP000", "TFP008"} <= set(ids(report))


def test_suppression_is_specific_to_the_rule(scan: Scan) -> None:
    report = scan('# tfpolicy:ignore TFP001 reason="unrelated"\n' + KV)
    assert "TFP008" in ids(report)


def test_xml_suppression_comment(scan: Scan) -> None:
    base = 'variable "a" {\n  type        = string\n  description = "d"\n}\n'
    xml = '<!-- tfpolicy:ignore TFP020 reason="test fixture" --><policies></policies>'
    assert "TFP020" not in ids(scan({"main.tf": base, "p.xml": xml}))


def test_parse_errors_become_critical_findings(scan: Scan) -> None:
    report = scan(
        {"main.tf": 'resource "a" "b" {\n  x = "oops\n}\n', "ok.tf": 'variable "v" {}\n'},
        header=False,
    )
    parse = [f for f in report.findings if f.rule_id == "TFP-PARSE"]
    assert parse and parse[0].severity == "critical" and parse[0].line >= 1


def test_findings_are_sorted_by_severity_then_location(scan: Scan) -> None:
    report = scan('resource "azurerm_cognitive_account" "a" {\n  name = "x"\n}\n' + KV)
    ranks = [severity_rank(f.severity) for f in report.findings]
    assert ranks == sorted(ranks, reverse=True)


def test_failing_threshold(scan: Scan) -> None:
    report = scan('resource "azurerm_resource_group" "r" {\n  tags = var.t\n}\n\nvariable "v" {}\n')
    assert report.failing("low") and not report.failing("critical")


def test_disabled_rules_do_not_run(scan: Scan) -> None:
    cfg = Config(disabled={"TFP008": "covered by the platform team"})
    report = scan(KV, cfg=cfg)
    assert "TFP008" not in ids(report) and "TFP008" not in report.rules_run
    assert report.disabled == {"TFP008": "covered by the platform team"}


def test_config_load_defaults_and_file(tmp_path: Path) -> None:
    assert Config.load(None).fail_on == "medium"
    assert Config.load(tmp_path / "missing.toml").paths == ["terraform"]
    f = tmp_path / "c.toml"
    f.write_text(
        '[tfpolicy]\npaths = ["infra"]\nfail_on = "high"\nrequired_tags = ["team"]\n[tfpolicy.disabled]\nTFP015 = "tags are applied by policy"\n',
        encoding="utf-8",
    )
    cfg = Config.load(f)
    assert (cfg.paths, cfg.fail_on, cfg.required_tags) == (["infra"], "high", ["team"])
    assert cfg.disabled == {"TFP015": "tags are applied by policy"}


def test_config_rejects_bad_severity_and_unexplained_disable(tmp_path: Path) -> None:
    bad = tmp_path / "a.toml"
    bad.write_text('[tfpolicy]\nfail_on = "urgent"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="fail_on"):
        Config.load(bad)
    silent = tmp_path / "b.toml"
    silent.write_text("[tfpolicy.disabled]\n", encoding="utf-8")
    silent.write_text('[tfpolicy]\n[tfpolicy.disabled]\nTFP001 = " "\n', encoding="utf-8")
    with pytest.raises(ValueError, match="written reason"):
        Config.load(silent)


def test_module_discovery_skips_hidden_and_vendored_dirs(tmp_path: Path) -> None:
    for d in ["a", "b/c", ".terraform/modules/x", ".git/hooks", "node_modules/p"]:
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "main.tf").write_text("", encoding="utf-8")
    found = discover_modules([tmp_path])
    assert sorted(p.relative_to(tmp_path).as_posix() for p in found) == ["a", "b/c"]
    single = tmp_path / "a" / "main.tf"
    assert discover_modules([single]) == [tmp_path / "a"]


def test_load_module_collects_policy_and_tfvars_files(tmp_path: Path) -> None:
    (tmp_path / "main.tf").write_text('variable "a" {}\n', encoding="utf-8")
    (tmp_path / "p.xml.tftpl").write_text("<policies/>", encoding="utf-8")
    (tmp_path / "x.tfvars").write_text("a = 1\n", encoding="utf-8")
    view, errors = load_module(tmp_path)
    assert not errors and len(view.files) == 1
    assert {p.name for p in view.other_files} == {"p.xml.tftpl", "x.tfvars"}
    assert [b.address for b in view.of_type("variable")] == ["var.a"]
    assert view.resources() == []
