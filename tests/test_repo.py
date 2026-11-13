"""Invariants over the real Terraform in this repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from tfpolicy import report
from tfpolicy.engine import Config, all_rules, load_module, run
from tfpolicy.fmt import check_paths

ENVS = ["dev", "prod"]


def test_repository_terraform_passes_every_rule(repo_root: Path) -> None:
    cfg = Config.load(repo_root / "tfpolicy.toml")
    rep = run([repo_root / "terraform"], cfg, base=repo_root)
    assert [f.to_dict() for f in rep.active] == []
    assert len(rep.modules) == 9


def test_every_suppression_in_the_repository_is_justified(repo_root: Path) -> None:
    cfg = Config.load(repo_root / "tfpolicy.toml")
    rep = run([repo_root / "terraform"], cfg, base=repo_root)
    assert {f.rule_id for f in rep.suppressed} == {"TFP008", "TFP017"}
    assert all(len(f.reason) > 40 for f in rep.suppressed)
    assert cfg.disabled == {}


def test_repository_terraform_is_canonically_formatted(repo_root: Path) -> None:
    assert [str(i) for i in check_paths([repo_root / "terraform"])] == []


def test_environment_roots_are_identical_in_shape(repo_root: Path) -> None:
    envs = repo_root / "terraform" / "envs"
    for name in ["main.tf", "variables.tf", "providers.tf", "outputs.tf"]:
        assert (envs / "dev" / name).read_text(encoding="utf-8") == (
            envs / "prod" / name
        ).read_text(encoding="utf-8")


@pytest.mark.parametrize("env", ENVS)
def test_tfvars_set_exactly_the_required_variables(repo_root: Path, env: str) -> None:
    d = repo_root / "terraform" / "envs" / env
    view, _ = load_module(d)
    required = {b.labels[0] for b in view.of_type("variable") if b.expr("default") is None}
    tfvars = parse_file_less(d / f"{env}.tfvars")
    # subscription_id is supplied by the pipeline as TF_VAR_subscription_id
    assert required - {"subscription_id"} <= tfvars
    declared = {b.labels[0] for b in view.of_type("variable")}
    assert tfvars <= declared


def parse_file_less(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s and not line.startswith((" ", "\t")):
            names.add(s.split("=", 1)[0].strip())
    return names


def test_prod_is_stricter_than_dev(repo_root: Path) -> None:
    def val(env: str, key: str) -> str:
        for line in (
            (repo_root / "terraform" / "envs" / env / f"{env}.tfvars")
            .read_text(encoding="utf-8")
            .splitlines()
        ):
            if line.startswith(key):
                return line.split("=", 1)[1].strip().strip('"')
        raise AssertionError(key)

    assert val("prod", "policy_effect") == "Deny"
    assert int(val("prod", "log_retention_days")) >= int(val("dev", "log_retention_days"))
    assert val("prod", "address_space") != val("dev", "address_space")


def test_every_module_declares_what_it_outputs_and_describes_it(repo_root: Path) -> None:
    for d in sorted((repo_root / "terraform" / "modules").iterdir()):
        view, _ = load_module(d)
        assert view.of_type("output"), d.name
        for out in view.of_type("output"):
            assert out.expr("description") is not None, f"{d.name}.{out.labels[0]}"


def test_policy_xml_template_variables_are_all_supplied(repo_root: Path) -> None:
    import re

    mod = repo_root / "terraform" / "modules" / "ai_gateway"
    template = (mod / "policies" / "openai-gateway.xml.tftpl").read_text(encoding="utf-8")
    used = set(re.findall(r"\$\{([a-z_]+)\}", template))
    main = (mod / "main.tf").read_text(encoding="utf-8")
    block = main[main.index("templatefile(") : main.index("})", main.index("templatefile("))]
    supplied = set(re.findall(r"^\s+([a-z_]+)\s+=", block, flags=re.M))
    assert used == supplied


def test_docs_list_every_rule_and_match_the_generated_reference(repo_root: Path) -> None:
    doc = (repo_root / "docs" / "policies.md").read_text(encoding="utf-8")
    assert doc == report.rules_markdown()
    for r in all_rules():
        assert r.id in doc


def test_compliance_mapping_mentions_every_rule(repo_root: Path) -> None:
    text = (repo_root / "docs" / "compliance-mapping.md").read_text(encoding="utf-8")
    missing = [r.id for r in all_rules() if r.id not in text]
    assert missing == []


def test_adrs_are_numbered_and_complete(repo_root: Path) -> None:
    adrs = sorted((repo_root / "docs" / "adr").glob("*.md"))
    assert [p.name[:4] for p in adrs] == [f"{i:04d}" for i in range(1, len(adrs) + 1)]
    for p in adrs:
        text = p.read_text(encoding="utf-8")
        for heading in ("## Status", "## Context", "## Decision", "## Consequences"):
            assert heading in text, f"{p.name} lacks {heading}"
