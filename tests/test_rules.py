from __future__ import annotations

from collections.abc import Callable

import pytest

from tfpolicy.engine import Config, Report, all_rules

from .conftest import ids

Scan = Callable[..., Report]

OPENAI_OK = """
resource "azurerm_cognitive_account" "this" {
  name                          = "x"
  custom_subdomain_name         = "x"
  public_network_access_enabled = false
  local_auth_enabled            = false
  tags                          = var.tags
}
"""

# rule id -> (violating module, compliant module)
CASES: dict[str, tuple[str, str]] = {
    "TFP001": (
        'resource "azurerm_cognitive_account" "a" {\n  public_network_access_enabled = true\n}\n',
        'resource "azurerm_cognitive_account" "a" {\n  public_network_access_enabled = false\n}\n',
    ),
    "TFP002": (
        'resource "azurerm_cognitive_account" "a" {\n  name = "x"\n}\n',
        'resource "azurerm_cognitive_account" "a" {\n  local_auth_enabled = false\n}\n',
    ),
    "TFP003": (
        'resource "azurerm_cognitive_account" "a" {\n  name = "x"\n}\n',
        'resource "azurerm_cognitive_account" "a" {\n  custom_subdomain_name = "x"\n}\n',
    ),
    "TFP004": (
        'resource "azurerm_key_vault" "k" {\n  purge_protection_enabled   = false\n  soft_delete_retention_days = 3\n}\n',
        'resource "azurerm_key_vault" "k" {\n  purge_protection_enabled   = true\n  soft_delete_retention_days = 90\n}\n',
    ),
    "TFP005": (
        'resource "azurerm_key_vault" "k" {\n  name = "k"\n}\n',
        'resource "azurerm_key_vault" "k" {\n  rbac_authorization_enabled    = true\n  public_network_access_enabled = false\n}\n',
    ),
    "TFP006": (
        'resource "azurerm_storage_account" "s" {\n  name = "s"\n}\n',
        'resource "azurerm_storage_account" "s" {\n  min_tls_version                 = "TLS1_2"\n  allow_nested_items_to_be_public = false\n'
        "  shared_access_key_enabled       = false\n  public_network_access_enabled   = false\n}\n",
    ),
    "TFP007": (
        'resource "azurerm_private_endpoint" "p" {\n  name = "p"\n}\n',
        'resource "azurerm_private_endpoint" "p" {\n  name = "p"\n\n  private_dns_zone_group {\n    name = "z"\n  }\n}\n',
    ),
    "TFP008": (
        'resource "azurerm_key_vault" "k" {\n  name = "k"\n}\n',
        'resource "azurerm_key_vault" "k" {\n  name = "k"\n}\n\nresource "azurerm_private_endpoint" "p" {\n'
        "  private_service_connection {\n    private_connection_resource_id = azurerm_key_vault.k.id\n  }\n}\n",
    ),
    "TFP009": (
        'resource "azurerm_key_vault" "k" {\n  name = "k"\n}\n',
        'resource "azurerm_key_vault" "k" {\n  name = "k"\n}\n\nresource "azurerm_monitor_diagnostic_setting" "d" {\n'
        "  target_resource_id         = azurerm_key_vault.k.id\n  log_analytics_workspace_id = var.law\n}\n",
    ),
    "TFP010": (
        'resource "azurerm_x" "a" {\n  administrator_password = "hunter2"\n}\n',
        'resource "azurerm_x" "a" {\n  administrator_password = var.pw\n}\n',
    ),
    "TFP011": (
        'variable "db_password" {\n  type = string\n}\n',
        'variable "db_password" {\n  type        = string\n  description = "d"\n  sensitive   = true\n}\n',
    ),
    "TFP013": (
        'resource "azurerm_network_security_group" "n" {\n  security_rule {\n    direction = "Inbound"\n    access = "Allow"\n'
        '    source_address_prefix = "*"\n  }\n}\n',
        'resource "azurerm_network_security_group" "n" {\n  security_rule {\n    direction = "Inbound"\n    access = "Allow"\n'
        '    source_address_prefix = "VirtualNetwork"\n  }\n}\n',
    ),
    "TFP014": (
        'resource "azurerm_subnet" "s" {\n  name = "s"\n}\n',
        'resource "azurerm_subnet" "s" {\n  name = "s"\n}\n\nresource "azurerm_subnet_network_security_group_association" "a" {\n'
        "  subnet_id = azurerm_subnet.s.id\n}\n",
    ),
    "TFP015": (
        'resource "azurerm_resource_group" "r" {\n  name = "r"\n}\n',
        'resource "azurerm_resource_group" "r" {\n  tags = var.tags\n}\n',
    ),
    "TFP016": (
        'resource "azurerm_cognitive_deployment" "d" {\n  name = "d"\n}\n',
        'resource "azurerm_cognitive_deployment" "d" {\n  rai_policy_name = "p"\n}\n',
    ),
    "TFP019": (
        'resource "azurerm_api_management" "a" {\n  virtual_network_type = "None"\n}\n',
        'resource "azurerm_api_management" "a" {\n  virtual_network_type = "Internal"\n}\n',
    ),
    "TFP021": (
        'resource "azurerm_private_dns_zone" "z" {\n  name = "z"\n}\n',
        'resource "azurerm_private_dns_zone" "z" {\n  name = "z"\n}\n\nresource "azurerm_private_dns_zone_virtual_network_link" "l" {\n'
        "  private_dns_zone_name = azurerm_private_dns_zone.z.name\n}\n",
    ),
    "TFP022": (
        'resource "azurerm_role_assignment" "r" {\n  role_definition_name = "Owner"\n}\n',
        'resource "azurerm_role_assignment" "r" {\n  role_definition_name = "Reader"\n  principal_type       = "User"\n}\n',
    ),
    "TFP023": (
        'resource "azurerm_resource_group" "r" {\n  name = var.nope\n}\n',
        'variable "n" {\n  type        = string\n  description = "d"\n}\n\nresource "azurerm_resource_group" "r" {\n  name = var.n\n}\n',
    ),
}


def test_every_rule_has_a_case_or_a_dedicated_test() -> None:
    dedicated = {"TFP012", "TFP017", "TFP018", "TFP020", "TFP024"}
    covered = set(CASES) | dedicated
    assert {r.id for r in all_rules()} == covered


@pytest.mark.parametrize("rule_id", sorted(CASES))
def test_rule_flags_the_violation_and_accepts_the_fix(
    rule_id: str, scan: Scan, tmp_path_factory: pytest.TempPathFactory
) -> None:
    bad, good = CASES[rule_id]
    assert rule_id in ids(scan(bad))
    # a fresh directory for the compliant variant
    from tfpolicy.engine import run

    d = tmp_path_factory.mktemp("good")
    from .conftest import TERRAFORM_HEADER

    (d / "main.tf").write_text(TERRAFORM_HEADER + good, encoding="utf-8")
    assert rule_id not in ids(run([d], Config(), base=d))


def test_rule_metadata_is_complete() -> None:
    for r in all_rules():
        assert r.title and r.rationale and r.remediation and r.benchmark
        assert r.severity in {"info", "low", "medium", "high", "critical"}


def test_tfp010_flags_secret_text_in_any_file(scan: Scan) -> None:
    report = scan(
        {
            "main.tf": 'resource "azurerm_resource_group" "r" {\n  tags = var.t\n}\n',
            "notes.json": '{"k": "-----BEGIN RSA PRIVATE KEY-----"}',
            "conn.tfvars": 'c = "AccountKey=abcdefghijklmnopqrstuvwxyz0123"',
        }
    )
    messages = [f.message for f in report.active if f.rule_id == "TFP010"]
    assert any("private key" in m for m in messages)
    assert any("storage account key" in m for m in messages)


def test_tfp010_flags_secret_default_and_nested_literal(scan: Scan) -> None:
    report = scan(
        'variable "api_key" {\n  type        = string\n  description = "d"\n  sensitive   = true\n  default     = "abc"\n}\n\n'
        'resource "azurerm_x" "a" {\n  nested {\n    client_secret = "s3cret"\n  }\n}\n'
    )
    msgs = " ".join(f.message for f in report.active if f.rule_id == "TFP010")
    assert "default value" in msgs and "client_secret" in msgs


def test_tfp010_ignores_names_that_only_look_secret(scan: Scan) -> None:
    report = scan(
        'resource "azurerm_x" "a" {\n  key_vault_key_id = "id"\n  secret_name = "n"\n  token_ttl = "1h"\n}\n'
    )
    assert "TFP010" not in ids(report)


def test_tfp011_flags_missing_type_description_and_unmarked_output(scan: Scan) -> None:
    report = scan('variable "v" {}\n\noutput "client_secret" {\n  value = "x"\n}\n')
    msgs = [f.message for f in report.active if f.rule_id == "TFP011"]
    assert {
        "variable has no type",
        "variable has no description",
        "secret-like output must set sensitive = true",
    } <= set(msgs)


def test_tfp012_requires_pinned_versions(scan: Scan) -> None:
    assert "TFP012" in ids(
        scan('resource "azurerm_resource_group" "r" {\n  tags = var.t\n}\n', header=False)
    )
    unpinned = 'terraform {\n  required_providers {\n    azurerm = {\n      source = "hashicorp/azurerm"\n    }\n  }\n}\n'
    msgs = [f.message for f in scan(unpinned, header=False).active if f.rule_id == "TFP012"]
    assert any("required_version" in m for m in msgs) and any("azurerm" in m for m in msgs)
    assert "TFP012" in ids(scan('terraform {\n  required_version = ">= 1.9.0"\n}\n', header=False))
    assert "TFP012" not in ids(scan('variable "a" {\n  type = string\n  description = "d"\n}\n'))


def test_tfp013_flags_multiple_sources_and_standalone_rules(scan: Scan) -> None:
    sources = (
        'resource "azurerm_network_security_rule" "r" {\n  direction = "Inbound"\n  access = "Allow"\n'
        '  source_address_prefixes = ["10.0.0.0/8", "Internet"]\n}\n'
    )
    assert "TFP013" in ids(scan(sources))
    outbound = 'resource "azurerm_network_security_rule" "r" {\n  direction = "Outbound"\n  access = "Allow"\n  source_address_prefix = "*"\n}\n'
    deny = 'resource "azurerm_network_security_rule" "r" {\n  direction = "Inbound"\n  access = "Deny"\n  source_address_prefix = "*"\n}\n'
    assert "TFP013" not in ids(scan(outbound))
    assert "TFP013" not in ids(scan(deny))


def test_tfp015_checks_required_keys_in_locals(scan: Scan) -> None:
    report = scan('locals {\n  tags = {\n    environment = "dev"\n  }\n}\n')
    msgs = [f.message for f in report.active if f.rule_id == "TFP015"]
    assert msgs and "owner" in msgs[0] and "cost-center" in msgs[0]
    full = 'locals {\n  tags = {\n    environment = "d"\n    owner = "o"\n    cost-center = "c"\n    data-classification = "x"\n  }\n}\n'
    assert "TFP015" not in ids(scan(full))
    custom = scan(full, cfg=Config(required_tags=["environment", "team"]))
    assert "TFP015" in ids(custom)


def test_tfp017_requires_azuread_backend_in_roots(scan: Scan) -> None:
    root = 'provider "azurerm" {\n  features {}\n}\n'
    assert "TFP017" in ids(scan(root))
    no_aad = root + 'terraform {\n  backend "azurerm" {\n    key = "k"\n  }\n}\n'
    assert "TFP017" in ids(scan(no_aad))
    local_backend = root + 'terraform {\n  backend "local" {}\n}\n'
    assert "TFP017" in ids(scan(local_backend))
    ok = root + 'terraform {\n  backend "azurerm" {\n    use_azuread_auth = true\n  }\n}\n'
    assert "TFP017" not in ids(scan(ok))
    assert "TFP017" not in ids(scan('variable "a" {\n  type = string\n  description = "d"\n}\n'))


def test_tfp018_requires_guardrails_in_environment_roots(
    scan: Scan, tmp_path_factory: pytest.TempPathFactory
) -> None:
    from tfpolicy.engine import run

    from .conftest import TERRAFORM_HEADER

    def env_root(body: str) -> list[str]:
        d = tmp_path_factory.mktemp("w") / "envs" / "dev"
        d.mkdir(parents=True)
        (d / "main.tf").write_text(
            TERRAFORM_HEADER + 'provider "azurerm" {\n  features {}\n}\n' + body, encoding="utf-8"
        )
        return ids(run([d], Config(), base=d))

    assert "TFP018" in env_root("")
    assert "TFP018" not in env_root('module "g" {\n  source = "../../modules/guardrails"\n}\n')


def test_tfp020_gateway_policy_content(scan: Scan) -> None:
    good = "<policies><inbound><validate-jwt /><llm-token-limit /><authentication-managed-identity /></inbound></policies>"
    base = 'variable "a" {\n  type = string\n  description = "d"\n}\n'
    assert "TFP020" not in ids(scan({"main.tf": base, "p.xml.tftpl": good}))
    for broken, expect in [
        (good.replace("<validate-jwt />", ""), "validate-jwt"),
        (good.replace("<llm-token-limit />", ""), "token limit"),
        (good.replace("<authentication-managed-identity />", ""), "managed identity"),
        (good + '<set-header name="api-key" />', "key"),
        (good + "<authentication-basic />", "key"),
    ]:
        report = scan({"main.tf": base, "p.xml.tftpl": broken})
        assert any(expect in f.message for f in report.active if f.rule_id == "TFP020"), expect
    assert "TFP020" not in ids(scan({"main.tf": base, "other.xml": "<config/>"}))


def test_tfp023_checks_locals_modules_outputs_and_data(
    scan: Scan, tmp_path_factory: pytest.TempPathFactory
) -> None:
    from tfpolicy.engine import run

    from .conftest import TERRAFORM_HEADER

    root = tmp_path_factory.mktemp("w")
    (root / "child").mkdir()
    (root / "child" / "main.tf").write_text(
        TERRAFORM_HEADER
        + 'variable "a" {\n  type        = string\n  description = "d"\n}\n\noutput "o" {\n  description = "d"\n  value       = var.a\n}\n',
        encoding="utf-8",
    )
    (root / "main.tf").write_text(
        TERRAFORM_HEADER + 'module "c" {\n  source = "./child"\n  a      = "x"\n}\n\n'
        'data "azurerm_client_config" "current" {}\n\n'
        "locals {\n  ok = module.c.o\n  bad1 = local.missing\n  bad2 = module.c.nope\n  bad3 = module.ghost.x\n"
        "  bad4 = azurerm_resource_group.ghost.id\n  bad5 = data.azurerm_client_config.other.id\n"
        "  fine = data.azurerm_client_config.current.tenant_id\n}\n",
        encoding="utf-8",
    )
    msgs = " | ".join(
        f.message for f in run([root], Config(), base=root).active if f.rule_id == "TFP023"
    )
    for needle in [
        "local.missing",
        "no output 'nope'",
        "module.ghost",
        "azurerm_resource_group.ghost",
        "other",
    ]:
        assert needle in msgs
    assert "local.ok" not in msgs and "current" not in msgs


def test_tfp024_missing_and_unknown_module_arguments(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    from tfpolicy.engine import run

    from .conftest import TERRAFORM_HEADER

    root = tmp_path_factory.mktemp("w")
    (root / "child").mkdir()
    (root / "child" / "main.tf").write_text(
        TERRAFORM_HEADER
        + 'variable "need" {\n  type        = string\n  description = "d"\n}\n\nvariable "opt" {\n  type        = string\n  description = "d"\n  default     = "x"\n}\n',
        encoding="utf-8",
    )
    (root / "main.tf").write_text(
        TERRAFORM_HEADER
        + 'module "c" {\n  source   = "./child"\n  for_each = toset(["a"])\n  typo     = 1\n}\n\n'
        'module "remote" {\n  source = "hashicorp/consul/aws"\n}\n\nmodule "gone" {\n  source = "./nowhere"\n}\n',
        encoding="utf-8",
    )
    msgs = [f.message for f in run([root], Config(), base=root).active if f.rule_id == "TFP024"]
    assert "required variable 'need' is not passed" in msgs
    assert "module has no variable 'typo'" in msgs
    assert len(msgs) == 2
