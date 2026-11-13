# ADR 0001: Model and secret stores are reachable only over private endpoints

## Status

Accepted

## Context

A model account with a public endpoint can be called by anyone who obtains a credential, from
anywhere. Prompts and completions routinely contain customer data, so the exposure is the
data, not just the cost. Disabling public access also breaks legitimate callers unless they
have a private path and name resolution that leads to it.

## Decision

Azure OpenAI accounts, Key Vaults and the Terraform state account have
`public_network_access_enabled = false` (the state account is the single documented
exception, see ADR 0006). Each is reached through a private endpoint registered in a private
DNS zone that is linked to the environment's virtual network. Rules TFP001, TFP005, TFP007,
TFP008, TFP021 check the whole chain, because turning off public access without a private
path produces an outage, and a private endpoint without a DNS zone group silently resolves to
the public address.

## Consequences

- Callers must run inside the network or peer into it. Developer laptops reach the model
  through a VPN or a bastion, not directly.
- Private endpoints and DNS zones add cost and a few minutes to a deployment.
- The network spoke must be peered to a hub that resolves the `privatelink` zones. The
  runbook says so, and the checker verifies the zones are linked.
- Debugging needs network tooling: a failing call is often DNS, not the service.
