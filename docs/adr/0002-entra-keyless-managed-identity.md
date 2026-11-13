# ADR 0002: No API keys; callers and services authenticate with Microsoft Entra ID

## Status

Accepted

## Context

API keys for a model account cannot be scoped to a caller, cannot be attributed to a person
and tend to leak into logs, tickets and chat. Rotation is manual and breaks callers. Entra ID
tokens are short-lived, carry an identity and are revoked centrally.

## Decision

`local_auth_enabled = false` on every Cognitive account. Callers hold a role assignment
(`Cognitive Services OpenAI User`) or, preferably, call the gateway, which holds the role
through a system-assigned managed identity. The gateway validates inbound tokens against the
configured tenant and audience and presents its own token to the model. Role assignments name
a principal type and a role (TFP022). Key Vault uses RBAC, not access policies (TFP005).

## Consequences

- There is nothing to rotate and nothing to leak, which removes a whole class of incident.
- Local development needs an identity: `az login` plus a role assignment, or a dev gateway.
- A new caller is onboarded by an identity and a role assignment, both reviewable in a pull
  request, rather than by handing over a key.
- SDKs that only accept a key need a token provider. Most current SDKs support one.
