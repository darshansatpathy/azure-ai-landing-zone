# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's
[private vulnerability reporting](https://github.com/darshansatpathy/azure-ai-landing-zone/security/advisories/new)
for this repository. You should get an acknowledgement within three working days.

## Scope

In scope: the Terraform modules, the policy checker (`src/tfpolicy`), the workflows and the documentation of the controls. Out of scope: Azure platform vulnerabilities, and the configuration of your own subscription, network hub and identity provider.

## Operating it safely

- The committed `dev.tfvars` and `prod.tfvars` hold non-secret settings only. Never put a secret in a variable file or a default (TFP010 and TFP011 check this). `backend.hcl`, `bootstrap.tfvars`, state files and plans are ignored by `.gitignore`; keep it that way.
- Deploy with workload identity federation (OIDC). Do not create client secrets for the pipeline.
- Keep the Azure Policy assignments at the highest scope you control and alert on changes to them.
- Review every `tfpolicy:ignore` in a pull request. `tfpolicy check --format markdown` lists them all with their reasons.
