# Compliance mapping

How each policy rule supports common control frameworks. This is an aid for audit
conversations. It is not a certification and not legal advice; verify wording against the
current official text of each framework before you cite it.

MCSB is the Microsoft cloud security benchmark. ISO references are ISO/IEC 27001:2022 Annex A
unless noted.

| Rule | What it enforces | MCSB | ISO/IEC 27001:2022 |
|---|---|---|---|
| TFP000 | Every exception carries a written reason | n/a | A.5.36 |
| TFP001 | No public network access to model accounts | NS-2 | A.8.20, A.8.22 |
| TFP002 | No key authentication on model accounts | IM-1 | A.5.15, A.8.5 |
| TFP003 | Custom subdomain, required for Entra ID | IM-1 | A.8.5 |
| TFP004 | Purge protection and soft delete on vaults | DP-8 | A.8.24 |
| TFP005 | Vault RBAC and no public access | IM-1, NS-2 | A.5.15, A.8.3 |
| TFP006 | Hardened storage: TLS 1.2, no shared keys, no anonymous blobs | DP-3, NS-2 | A.8.24, A.8.3 |
| TFP007 | Private endpoints register in private DNS | NS-1 | A.8.20 |
| TFP008 | Every data service has a private endpoint | NS-2 | A.8.20, A.8.22 |
| TFP009 | Diagnostic logs to Log Analytics | LT-3 | A.8.15, A.8.16 |
| TFP010 | No credentials in code | IM-8 | A.5.17, A.8.28 |
| TFP011 | Typed, described variables; secrets marked sensitive | n/a | A.8.28 |
| TFP012 | Pinned Terraform and provider versions | n/a | A.8.9, A.8.32 |
| TFP013 | No inbound allow rule from the internet | NS-1 | A.8.20, A.8.22 |
| TFP014 | A network security group on every subnet | NS-1 | A.8.22 |
| TFP015 | Required tags for ownership and classification | n/a | A.5.9, A.5.12 |
| TFP016 | A named content filter on every deployment | n/a | ISO/IEC 42001 A.6 |
| TFP017 | Remote state with Entra ID authentication | DP-3, IM-1 | A.8.24, A.8.5 |
| TFP018 | Preventive Azure Policy applied in every environment | PV-2 | A.8.9 |
| TFP019 | Gateway injected into the network, internal only | NS-1, NS-2 | A.8.20, A.8.22 |
| TFP020 | Gateway authenticates callers, limits tokens, uses managed identity | IM-1 | A.8.5, ISO/IEC 42001 A.6 |
| TFP021 | Private DNS zones linked to the network | NS-1 | A.8.20 |
| TFP022 | Role assignments name a principal type; no broad roles | PA-7 | A.5.18, A.8.2 |
| TFP023 | Every reference resolves | n/a | A.8.29, A.8.32 |
| TFP024 | Module calls match the module interface | n/a | A.8.29, A.8.32 |

## Using this in an audit

1. Run `tfpolicy check --format markdown` and attach the output. It lists findings, every
   suppression with its reason, and any disabled rule with its reason.
2. Show the SARIF results in GitHub code scanning for the history of findings per pull request.
3. Point to the Azure Policy assignments in the portal for the preventive layer.
