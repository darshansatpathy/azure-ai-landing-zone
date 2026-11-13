# ADR 0005: Enforce in code review and again in the platform

## Status

Accepted

## Context

A check in CI only protects changes that go through CI. Portal edits, CLI commands, other
pipelines and compromised credentials all bypass it. A runtime control that is not also
checked in code produces surprises at deployment time.

## Decision

Two layers with the same intent. `tfpolicy` and the other CI checks reject bad Terraform in
the pull request. The `guardrails` module defines Azure Policy and assigns it in every
environment root (TFP018): deny public network access and key authentication on Cognitive
accounts, require tags, restrict regions. In dev the effect is `Audit`, so engineers see what
would be blocked without stopping experiments. In prod it is `Deny`.

## Consequences

- A change made outside Terraform is refused or flagged by the platform.
- Policy definitions are Terraform too, so they are reviewed, versioned and promoted the same way.
- Two sets of rules can drift. The compliance mapping documents both, and a test requires it
  to mention every `tfpolicy` rule ID; any other difference is a bug to fix in review.
- Remediation of existing non-compliant resources is a separate decision (`DeployIfNotExists`
  and remediation tasks are intentionally out of scope).
