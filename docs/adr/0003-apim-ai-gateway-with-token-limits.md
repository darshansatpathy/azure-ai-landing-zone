# ADR 0003: An API Management gateway sits in front of the model

## Status

Accepted

## Context

Calling the model account directly gives no per-caller budget, no uniform audit trail and no
place to change behaviour without touching every application. One runaway agent loop can
exhaust the quota for every other workload. Model usage is billed per token, so an unbounded
caller is an unbounded cost.

## Decision

Deploy API Management in internal virtual-network mode (TFP019) and route all callers through
it. The gateway policy, kept as a template in `ai_gateway/policies/`, validates the caller's
token, applies `llm-token-limit` per calling identity, emits token metrics, and authenticates
to the model with its managed identity, replacing the caller's `Authorization` header. TFP020
fails the build if the `validate-jwt`, token-limit or managed-identity statement is removed,
or if the policy forwards an `api-key` header or basic credentials.

Alternatives considered: calling the account directly (no budgets), an application-level
library in each service (inconsistent, bypassable), and a self-hosted proxy (more to patch
and scale). API Management costs more at low volume but is the managed option that already
integrates with the network, identity and monitoring in use.

## Consequences

- The gateway is a hop and a dependency. Premium in production gives zonal redundancy and an
  SLA; Developer in dev has neither.
- API Management in internal mode takes 30 to 60 minutes to provision and bills hourly.
- Per-caller token budgets turn a cost incident into a 429 for one caller.
- Gateway logs, not model-account logs, are the system of record for who asked what.
