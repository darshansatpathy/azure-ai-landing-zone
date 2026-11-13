# Threat model

Scope: the data path from a caller to a model account, and the control plane that manages it.
The method is STRIDE per trust boundary. "Evidence" names the rule or test that fails if the
control is removed.

## Trust boundaries

1. Internet to the virtual network. Nothing is meant to cross it inbound.
2. Caller to gateway, inside the network.
3. Gateway to model account over the private endpoint.
4. Operators and pipelines to Azure Resource Manager.

## Threats and controls

| # | Threat | Control | Evidence |
|---|---|---|---|
| T1 | Someone reaches the model from the internet with a stolen key | No public network access, no keys, private endpoint only | TFP001, TFP002, TFP008; Azure Policy `deny-ai-public-network`, `deny-ai-local-auth` |
| T2 | A leaked bearer token is replayed | Short-lived Entra tokens, audience and issuer checked, `require-expiration-time` | TFP020 |
| T3 | One tenant or agent consumes the whole quota (denial of service, runaway loop) | Per-caller token limit at the gateway | TFP020 |
| T4 | A credential is committed to the repository | No secret literals in resources or variable defaults; pattern scan of module files | TFP010 |
| T5 | A deployer reopens public access in the portal | Azure Policy denies it in prod, audits it in dev | TFP018, `modules/guardrails` |
| T6 | An operator deletes the vault and its keys | Purge protection, soft delete 90 days, state lock | TFP004 |
| T7 | Lateral movement from a compromised workload subnet | One NSG per subnet, no inbound rule from the internet, private DNS | TFP013, TFP014 |
| T8 | Nobody can reconstruct who called what | Gateway and account logs to Log Analytics, 90+ days | TFP009 |
| T9 | Terraform state exposes secrets or is tampered with | State in a locked, versioned account, Entra ID auth, no shared keys | TFP017, TFP006 |
| T10 | A provider update changes behaviour between plan and apply | Version constraints, `terraform validate` in CI | TFP012 |
| T11 | A reviewer misses a risky change in a large diff | The checker runs on every pull request and uploads SARIF to code scanning | `ci.yml` |
| T12 | The gateway forwards a caller-supplied key or basic credentials to the model | Policy replaces `Authorization` with the gateway's managed-identity token and the checker rejects `api-key` or basic-auth forwarding | TFP020 |

## Residual risk and what is out of scope

- **Prompt injection and unsafe agent actions** happen above this layer. See
  [agent-guardrails-gateway](https://github.com/darshansatpathy/agent-guardrails-gateway),
  which enforces policy at the tool boundary.
- **Content safety** is configured per deployment through `rai_policy_name`. The filter level
  is a product decision, and the code only guarantees that one is named.
- **A malicious insider with Owner on the subscription** can remove policy assignments. Put
  assignments at management-group scope and alert on policy changes in your landing zone.
- **Azure platform vulnerabilities** are outside this repository's control.
- **The state storage account** is reachable on its public endpoint, restricted by firewall
  and Entra ID, because CI runners are public. Self-hosted runners would allow a private
  endpoint. The exception is recorded in the code with its reason.
