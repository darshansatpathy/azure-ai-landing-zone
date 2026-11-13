# ADR 0006: Identical environment roots, remote state with Entra ID authentication

## Status

Accepted

## Context

Environments that are written separately diverge, and the divergence is found during an
incident. State that lives on a laptop is lost or leaked. State access that uses a storage
account key cannot be attributed or revoked per person.

## Decision

Each environment is a thin root module (`terraform/envs/dev`, `prod`) with identical `.tf`
files. Only the `.tfvars` differ. A test asserts the files are identical and that prod is
stricter than dev (policy effect, SKU, retention). State is stored in an Azure Storage
account created by `terraform/bootstrap`, with versioning, soft delete, a delete lock, shared
keys disabled and `use_azuread_auth = true`. Deployment uses GitHub OIDC federation, so no
credential is stored in the repository.

The state account keeps a public endpoint restricted by firewall and Entra ID because hosted
CI runners are public. This is the one documented suppression of TFP008, with its reason in
the code. Self-hosted runners in the network would remove it.

## Consequences

- Promotion is "same code, different values", which is easy to review and to reason about.
- Bootstrapping has a chicken-and-egg step (local state, then migrate). The runbook has it.
- The single exception is visible in `tfpolicy check --format markdown` for auditors.
