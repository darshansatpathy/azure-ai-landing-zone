"""The rule set. Each rule reads one Terraform module (a directory) and yields hits."""

from __future__ import annotations

import re
from collections.abc import Iterator

from .engine import Config, Hit, ModuleView, load_module, rule
from .hcl import Block, Expr

TAGGABLE = {
    "azurerm_resource_group",
    "azurerm_virtual_network",
    "azurerm_network_security_group",
    "azurerm_public_ip",
    "azurerm_key_vault",
    "azurerm_storage_account",
    "azurerm_cognitive_account",
    "azurerm_api_management",
    "azurerm_log_analytics_workspace",
    "azurerm_application_insights",
    "azurerm_private_endpoint",
    "azurerm_private_dns_zone",
    "azurerm_user_assigned_identity",
}
SECRET_NAME = re.compile(
    r"(?i)(^|_)(password|passwd|secret|api_?key|access_key|sas_token|connection_string|private_key)($|_value$)"
)
SECRET_TEXT = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "a private key"),
    (re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}"), "a storage account key"),
    (re.compile(r"(?i)sharedaccesssignature=|[?&]sig=[A-Za-z0-9%+/=]{20,}"), "a SAS token"),
]
PUBLIC_SOURCES = {"*", "internet", "0.0.0.0/0", "any"}


def _false(b: Block, name: str) -> bool:
    e = b.expr(name)
    return e is not None and e.is_false()


def _true(b: Block, name: str) -> bool:
    e = b.expr(name)
    return e is not None and e.is_true()


def _str(b: Block, name: str) -> str | None:
    e = b.expr(name)
    return e.string() if e else None


def _default_action_deny(b: Block, child: str) -> bool:
    c = b.child(child)
    if c is None:
        return False
    return (_str(c, "default_action") or "").lower() == "deny"


def _private_endpoint_targets(m: ModuleView) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for pe in m.resources("azurerm_private_endpoint"):
        for psc in pe.children("private_service_connection"):
            e = psc.expr("private_connection_resource_id")
            if e:
                out.update(e.refs())
    return out


def _refs_in(blocks: list[Block], attr: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for b in blocks:
        e = b.expr(attr)
        if e:
            out.update(e.refs())
    return out


@rule(
    "TFP001",
    "Azure OpenAI and other Cognitive accounts must not accept public network traffic",
    "critical",
    "A public endpoint lets anyone who obtains a key or token reach the model from the internet.",
    "Set public_network_access_enabled = false as a literal and reach the account through a "
    "private endpoint.",
    "MCSB NS-2",
)
def openai_no_public(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_cognitive_account"):
        if not _false(r, "public_network_access_enabled"):
            yield Hit("public_network_access_enabled must be the literal false", r)


@rule(
    "TFP002",
    "Cognitive accounts must disable key authentication",
    "high",
    "Static API keys cannot be scoped, rotated per caller or tied to a person, and leak in logs.",
    "Set local_auth_enabled = false and grant callers a data-plane role through Microsoft "
    "Entra ID.",
    "MCSB IM-1",
)
def openai_no_local_auth(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_cognitive_account"):
        if not _false(r, "local_auth_enabled"):
            yield Hit("local_auth_enabled must be the literal false (Entra ID only)", r)


@rule(
    "TFP003",
    "Cognitive accounts need a custom subdomain",
    "medium",
    "Microsoft Entra authentication and private endpoints both require a custom subdomain name.",
    "Set custom_subdomain_name.",
    "MCSB IM-1",
)
def openai_subdomain(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_cognitive_account"):
        if r.expr("custom_subdomain_name") is None:
            yield Hit("custom_subdomain_name is not set", r)


@rule(
    "TFP004",
    "Key Vaults must have purge protection and soft delete retention",
    "high",
    "Without purge protection a deleted vault, and every key in it, can be destroyed permanently.",
    "Set purge_protection_enabled = true and soft_delete_retention_days to at least 7.",
    "MCSB DP-8",
)
def keyvault_purge(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_key_vault"):
        if not _true(r, "purge_protection_enabled"):
            yield Hit("purge_protection_enabled must be true", r)
        days = r.expr("soft_delete_retention_days")
        n = days.number() if days else None
        if n is None or n < 7:
            yield Hit("soft_delete_retention_days must be a literal of at least 7", r)


@rule(
    "TFP005",
    "Key Vaults must use Azure RBAC and be closed to the public network",
    "high",
    "Access policies are not auditable per role, and an open vault firewall exposes secrets "
    "metadata.",
    "Set rbac_authorization_enabled = true and public_network_access_enabled = false.",
    "MCSB IM-1, NS-2",
)
def keyvault_rbac_private(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_key_vault"):
        if not _true(r, "rbac_authorization_enabled"):
            yield Hit("rbac_authorization_enabled must be true", r)
        if not _false(r, "public_network_access_enabled") and not _default_action_deny(
            r, "network_acls"
        ):
            yield Hit("close the public network or set network_acls default_action = Deny", r)


@rule(
    "TFP006",
    "Storage accounts must be hardened",
    "high",
    "Shared keys, anonymous blobs, old TLS and an open firewall are the common causes of "
    "data exposure.",
    "Set min_tls_version = TLS1_2, allow_nested_items_to_be_public = false, "
    "shared_access_key_enabled = false, and close the public network or deny by default.",
    "MCSB DP-3, NS-2",
)
def storage_hardening(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_storage_account"):
        if _str(r, "min_tls_version") != "TLS1_2":
            yield Hit('min_tls_version must be "TLS1_2"', r)
        if not _false(r, "allow_nested_items_to_be_public"):
            yield Hit("allow_nested_items_to_be_public must be false", r)
        if not _false(r, "shared_access_key_enabled"):
            yield Hit("shared_access_key_enabled must be false (Entra ID only)", r)
        if _false(r, "https_traffic_only_enabled"):
            yield Hit("https_traffic_only_enabled must not be false", r)
        if not _false(r, "public_network_access_enabled") and not _default_action_deny(
            r, "network_rules"
        ):
            yield Hit("close the public network or set network_rules default_action = Deny", r)


@rule(
    "TFP007",
    "Private endpoints must register in a private DNS zone",
    "medium",
    "Without a DNS zone group the service name still resolves to its public address.",
    "Add a private_dns_zone_group block with the matching privatelink zone.",
    "MCSB NS-1",
)
def pe_dns(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_private_endpoint"):
        if r.child("private_dns_zone_group") is None:
            yield Hit("private_dns_zone_group is missing", r)


@rule(
    "TFP008",
    "Every PaaS data service must have a private endpoint in the same module",
    "high",
    "Disabling public access is only useful if callers have a private path to the service.",
    "Add an azurerm_private_endpoint whose private_connection_resource_id references the resource.",
    "MCSB NS-2",
)
def paas_private_endpoint(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    targets = _private_endpoint_targets(m)
    for r in m.resources(
        "azurerm_cognitive_account", "azurerm_key_vault", "azurerm_storage_account"
    ):
        if (r.labels[0], r.labels[1]) not in targets:
            yield Hit(f"no private endpoint references {r.address}", r)


@rule(
    "TFP009",
    "Diagnostic settings must send logs and metrics to Log Analytics",
    "medium",
    "Without audit logs there is no evidence of who called the model or changed the vault.",
    "Add an azurerm_monitor_diagnostic_setting targeting the resource with a Log Analytics "
    "workspace.",
    "MCSB LT-3",
)
def diagnostics(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    covered = _refs_in(m.resources("azurerm_monitor_diagnostic_setting"), "target_resource_id")
    for r in m.resources(
        "azurerm_cognitive_account", "azurerm_key_vault", "azurerm_api_management"
    ):
        if (r.labels[0], r.labels[1]) not in covered:
            yield Hit(f"no diagnostic setting targets {r.address}", r)
    for d in m.resources("azurerm_monitor_diagnostic_setting"):
        if d.expr("log_analytics_workspace_id") is None:
            yield Hit("log_analytics_workspace_id is not set", d)


def _walk_attrs(b: Block) -> Iterator[tuple[str, Expr]]:
    for blk in b.walk():
        for name, a in blk.attrs.items():
            yield name, a.value


@rule(
    "TFP010",
    "No credentials in code",
    "critical",
    "Secrets committed to a repository are leaked to everyone with read access, forever.",
    "Use managed identities and Key Vault references. Never write a secret as a literal.",
    "MCSB IM-8",
)
def no_secrets(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for b in m.blocks:
        if b.type == "resource":
            for name, e in _walk_attrs(b):
                s = e.string()
                if SECRET_NAME.search(name) and s:
                    yield Hit(f"attribute {name!r} holds a literal credential", b, e.line)
        if b.type == "variable" and b.labels and SECRET_NAME.search(b.labels[0]):
            d = b.expr("default")
            if d is not None and d.string():
                yield Hit("a secret variable must not have a default value", b, d.line)
    for path, text in m.other_files.items():
        for pattern, what in SECRET_TEXT:
            if pattern.search(text):
                yield Hit(f"file appears to contain {what}", None, 1, path)


@rule(
    "TFP011",
    "Variables must be typed and described, and secrets must be sensitive",
    "low",
    "Untyped variables hide mistakes, and unmarked secrets are printed in plans and logs.",
    "Add type and description; set sensitive = true on secret variables and outputs.",
    "Terraform style guide",
)
def variables(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for b in m.of_type("variable"):
        if b.expr("type") is None:
            yield Hit("variable has no type", b)
        if b.expr("description") is None:
            yield Hit("variable has no description", b)
        if b.labels and SECRET_NAME.search(b.labels[0]) and not _true(b, "sensitive"):
            yield Hit("secret-like variable must set sensitive = true", b)
    for b in m.of_type("output"):
        if b.labels and SECRET_NAME.search(b.labels[0]) and not _true(b, "sensitive"):
            yield Hit("secret-like output must set sensitive = true", b)


_CONSTRAINT = re.compile(r"^\s*(~>|>=|=|<=|<|>)\s*\d")


@rule(
    "TFP012",
    "Terraform and provider versions must be constrained",
    "medium",
    "Unpinned providers change behaviour between runs and break reproducible plans.",
    "Set required_version and a versioned required_providers entry in every module.",
    "Supply chain hygiene",
)
def pinned(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    tf_blocks = m.of_type("terraform")
    if not tf_blocks:
        if m.blocks:
            yield Hit("module has no terraform block", None, 1, m.files[0].path)
        return
    for t in tf_blocks:
        rv = t.expr("required_version")
        s = rv.string() if rv else None
        if not s or not _CONSTRAINT.match(s):
            yield Hit("required_version must carry a version constraint", t)
        rp = t.child("required_providers")
        if rp is None:
            yield Hit("required_providers is missing", t)
            continue
        for name, attr in rp.attrs.items():
            obj = attr.value.as_object() or {}
            ver = obj.get("version")
            v = ver.string() if ver else None
            if not v or not _CONSTRAINT.match(v):
                yield Hit(f"provider {name!r} has no version constraint", rp, attr.line)


@rule(
    "TFP013",
    "Network security groups must not allow inbound traffic from the internet",
    "high",
    "An allow rule from any address exposes the subnet to scanning and brute force.",
    "Restrict source_address_prefix to a service tag or a known range.",
    "MCSB NS-1",
)
def nsg_open(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_network_security_group", "azurerm_network_security_rule"):
        rules = r.children("security_rule") or ([r] if r.labels[0].endswith("_rule") else [])
        for sr in rules:
            if (_str(sr, "direction") or "").lower() != "inbound":
                continue
            if (_str(sr, "access") or "").lower() != "allow":
                continue
            sources = [_str(sr, "source_address_prefix")]
            lst = sr.expr("source_address_prefixes")
            if lst and (items := lst.as_list()):
                sources += [i.string() for i in items]
            if any((s or "").lower() in PUBLIC_SOURCES for s in sources):
                yield Hit("inbound allow rule is open to the internet", r, sr.line)


@rule(
    "TFP014",
    "Every subnet needs a network security group",
    "medium",
    "A subnet without an NSG has no network-layer filtering at all.",
    "Add an azurerm_subnet_network_security_group_association for the subnet.",
    "MCSB NS-1",
)
def subnet_nsg(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    covered = _refs_in(
        m.resources("azurerm_subnet_network_security_group_association"), "subnet_id"
    )
    for r in m.resources("azurerm_subnet"):
        if (r.labels[0], r.labels[1]) not in covered:
            yield Hit(f"{r.address} has no NSG association", r)


@rule(
    "TFP015",
    "Resources must carry the required tags",
    "low",
    "Tags drive cost allocation, ownership and data classification, and policy depends on them.",
    "Set tags on every taggable resource and include the keys listed in tfpolicy.toml.",
    "Cloud Adoption Framework tagging",
)
def tags(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources(*sorted(TAGGABLE)):
        if r.expr("tags") is None:
            yield Hit("tags are not set", r)
    for loc in m.of_type("locals"):
        e = loc.expr("tags")
        obj = e.as_object() if e else None
        if obj is not None:
            missing = [k for k in cfg.required_tags if k not in obj]
            if missing:
                yield Hit(
                    f"local tags are missing: {', '.join(missing)}", loc, e.line if e else None
                )


@rule(
    "TFP016",
    "Model deployments must name a content filter policy",
    "medium",
    "Relying on the service default leaves the filtering level implicit and unreviewed.",
    "Set rai_policy_name on every azurerm_cognitive_deployment.",
    "Responsible AI",
)
def deployment_filter(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_cognitive_deployment"):
        if r.expr("rai_policy_name") is None:
            yield Hit("rai_policy_name is not set", r)


def _is_root(m: ModuleView) -> bool:
    return any(b.type == "provider" and b.labels[:1] == ("azurerm",) for b in m.blocks)


@rule(
    "TFP017",
    "Root modules must use a remote azurerm backend with Entra ID authentication",
    "high",
    "Local state holds secrets and breaks locking, and storage keys give broad access to state.",
    'Declare backend "azurerm" with use_azuread_auth = true.',
    "MCSB DP-3, IM-1",
)
def backend(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    if not _is_root(m):
        return
    terraform_blocks = m.of_type("terraform")
    backends = [be for t in terraform_blocks for be in t.children("backend")]
    if not backends:
        anchor = terraform_blocks[0] if terraform_blocks else None
        yield Hit('root module has no backend "azurerm"', anchor, None, m.files[0].path)
        return
    for be in backends:
        if be.labels[:1] != ("azurerm",):
            yield Hit('root module must use backend "azurerm"', be)
        elif not _true(be, "use_azuread_auth"):
            yield Hit("backend must set use_azuread_auth = true", be)


@rule(
    "TFP018",
    "Environment roots must apply the Azure Policy guardrails module",
    "medium",
    "Preventive policy stops a later change from reopening what Terraform closed.",
    "Call the guardrails module from every root under envs/.",
    "MCSB PV-2",
)
def guardrails_wired(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    if "envs" not in m.path.parts or not _is_root(m):
        return
    sources: list[str] = []
    for b in m.of_type("module"):
        src = b.expr("source")
        sources.append((src.string() or "") if src is not None else "")
    if not any(s.rstrip("/").endswith("guardrails") for s in sources):
        yield Hit("no module call to modules/guardrails", None, 1, m.files[0].path)


@rule(
    "TFP019",
    "API Management must be network-isolated",
    "high",
    "A public gateway in front of a private model is the new public endpoint.",
    'Set virtual_network_type = "Internal" and inject the gateway into its own subnet.',
    "MCSB NS-1, NS-2",
)
def apim_internal(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_api_management"):
        if _str(r, "virtual_network_type") != "Internal":
            yield Hit('virtual_network_type must be "Internal"', r)


@rule(
    "TFP020",
    "Gateway policy must authenticate callers, limit tokens and use managed identity",
    "high",
    "The gateway is where per-caller token budgets and keyless access to the model are enforced.",
    "Include validate-jwt, llm-token-limit and authentication-managed-identity, and never "
    "forward an api-key header.",
    "Responsible AI, MCSB IM-1",
)
def gateway_policy(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for path, text in m.other_files.items():
        if not (path.name.endswith(".xml") or path.name.endswith(".xml.tftpl")):
            continue
        if "<policies" not in text:
            continue
        if "<validate-jwt" not in text:
            yield Hit("policy has no validate-jwt", None, 1, path)
        if "<llm-token-limit" not in text and "<azure-openai-token-limit" not in text:
            yield Hit("policy has no token limit", None, 1, path)
        if "<authentication-managed-identity" not in text:
            yield Hit(
                "policy does not authenticate to the model with a managed identity", None, 1, path
            )
        if re.search(r'name="api-key"', text) or "<authentication-basic" in text:
            yield Hit("policy forwards a key or basic credentials", None, 1, path)


@rule(
    "TFP021",
    "Private DNS zones must be linked to a virtual network",
    "medium",
    "An unlinked zone resolves nothing, so clients fall back to the public address.",
    "Add an azurerm_private_dns_zone_virtual_network_link for the zone.",
    "MCSB NS-1",
)
def dns_links(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    linked = _refs_in(
        m.resources("azurerm_private_dns_zone_virtual_network_link"), "private_dns_zone_name"
    )
    for r in m.resources("azurerm_private_dns_zone"):
        if (r.labels[0], r.labels[1]) not in linked:
            yield Hit(f"{r.address} has no virtual network link", r)


@rule(
    "TFP022",
    "Role assignments must name a principal type and a built-in or custom role",
    "low",
    "An unset principal_type makes assignments slower to propagate and harder to audit.",
    "Set principal_type to ServicePrincipal, User or Group, and avoid the Owner role.",
    "MCSB PA-7",
)
def role_assignments(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for r in m.resources("azurerm_role_assignment"):
        if r.expr("principal_type") is None:
            yield Hit("principal_type is not set", r)
        role = _str(r, "role_definition_name")
        if role in {"Owner", "Contributor", "User Access Administrator"}:
            yield Hit(f"role {role!r} is too broad for a workload identity", r)


_META = {"source", "version", "for_each", "count", "providers", "depends_on"}
_MODULE_CACHE: dict[str, ModuleView | None] = {}


def _module_target(m: ModuleView, call: Block) -> ModuleView | None:
    src = call.expr("source")
    s = src.string() if src else None
    if not s or not s.startswith("."):
        return None
    target = (m.path / s).resolve()
    key = str(target)
    if key not in _MODULE_CACHE:
        _MODULE_CACHE[key] = load_module(target)[0] if target.is_dir() else None
    return _MODULE_CACHE[key]


@rule(
    "TFP023",
    "Every reference must resolve",
    "high",
    "A reference to an undeclared variable, local, module output or resource fails at plan time, "
    "after the pipeline has already started.",
    "Declare the variable, local, output or resource, or fix the name.",
    "Terraform validate",
)
def references_resolve(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    variables = {b.labels[0] for b in m.of_type("variable") if b.labels}
    local_names = {n for b in m.of_type("locals") for n in b.attrs}
    modules = {b.labels[0]: b for b in m.of_type("module") if b.labels}
    resources = {
        (b.labels[0], b.labels[1]) for b in m.blocks if b.type == "resource" and len(b.labels) == 2
    }
    data: dict[str, set[str]] = {
        f"data.{b.labels[0]}": set() for b in m.of_type("data") if len(b.labels) == 2
    }
    for b in m.of_type("data"):
        if len(b.labels) == 2:
            data[f"data.{b.labels[0]}"].add(b.labels[1])
    for top in m.blocks:
        for blk in top.walk():
            for attr in blk.attrs.values():
                for root, name, attribute in attr.value.traversals():
                    if root == "var" and name not in variables:
                        yield Hit(f"var.{name} is not declared", top, attr.line)
                    elif root == "local" and name not in local_names:
                        yield Hit(f"local.{name} is not declared", top, attr.line)
                    elif root == "module":
                        call = modules.get(name)
                        if call is None:
                            yield Hit(f"module.{name} is not declared", top, attr.line)
                            continue
                        target = _module_target(m, call)
                        outputs = (
                            {o.labels[0] for o in target.of_type("output")} if target else None
                        )
                        if attribute and outputs is not None and attribute not in outputs:
                            yield Hit(f"module.{name} has no output {attribute!r}", top, attr.line)
                    elif (root.startswith("azurerm_") and (root, name) not in resources) or (
                        root.startswith("data.azurerm_") and name not in data.get(root, set())
                    ):
                        yield Hit(f"{root}.{name} is not declared in this module", top, attr.line)


@rule(
    "TFP024",
    "Module calls must pass every required variable and nothing else",
    "high",
    "A missing required argument or an unknown one is a plan-time error.",
    "Pass each variable without a default, and remove arguments the module does not declare.",
    "Terraform validate",
)
def module_calls(m: ModuleView, cfg: Config) -> Iterator[Hit]:
    for call in m.of_type("module"):
        target = _module_target(m, call)
        if target is None:
            continue
        declared = {b.labels[0]: b for b in target.of_type("variable") if b.labels}
        required = {n for n, b in declared.items() if b.expr("default") is None}
        passed = set(call.attrs) - _META
        for name in sorted(required - passed):
            yield Hit(f"required variable {name!r} is not passed", call)
        for name in sorted(passed - set(declared)):
            yield Hit(f"module has no variable {name!r}", call)
