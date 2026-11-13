# ADR 0004: A small purpose-built policy checker, alongside the standard scanners

## Status

Accepted

## Context

Generic scanners (Checkov, tfsec, Trivy, Conftest with OPA) already cover broad Terraform
hygiene and should be used. They are weaker at rules that depend on *this* architecture:
that every PaaS resource has a private endpoint in the same module, that the gateway policy
contains the statements that make it a control, that references and module arguments
resolve. A custom rule in OPA or Checkov is possible, but it needs a language runtime in CI,
and the logic is hard for readers of this repository to follow in a review.

## Decision

Ship `tfpolicy`, a stdlib-only Python tool with a parser for the subset of HCL used here,
24 rules with severities, reasoned suppressions, SARIF output and a formatting check. It runs
in CI next to `terraform fmt`, `terraform validate` and CodeQL. It does not replace
Terraform's own validation; TFP023 and TFP024 let it fail fast and offline, `terraform
validate` stays the authority. Teams that already run Checkov or Conftest should keep them.

## Consequences

- The rules are documented, tested (including mutation-style tests that plant a defect and
  expect a finding) and readable in one sitting. They are also a template to port to OPA.
- We own the parser. It covers what these modules use, and it fails loudly with a line
  number on anything else rather than guessing. The limits are in the README.
- Suppressions need a written reason (TFP000), so exceptions are visible and reviewable.
