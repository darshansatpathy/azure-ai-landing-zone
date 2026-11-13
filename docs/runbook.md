# Runbook

## Prerequisites

- An Azure subscription and an identity that can create resources, policy definitions and
  role assignments for the first run (Owner, or Contributor plus User Access Administrator
  and Resource Policy Contributor).
- Terraform 1.9 or later, and the Azure CLI signed in (`az login`).
- A Microsoft Entra app registration whose identifier URI is the gateway audience.

## 1. Bootstrap remote state (once per subscription)

```bash
cd terraform/bootstrap
cp bootstrap.tfvars.example bootstrap.tfvars   # fill in names, your CI principal, runner IP ranges
terraform init
terraform apply -var-file=bootstrap.tfvars
terraform output backend_config
```

The first run uses local state because the backend does not exist yet. Migrate it:

```bash
# add this to terraform/bootstrap/main.tf terraform block, then:
#   backend "azurerm" { use_azuread_auth = true }
terraform init -migrate-state -backend-config=../envs/backend.hcl
rm terraform.tfstate terraform.tfstate.backup
```

## 2. Deploy an environment

```bash
cd terraform/envs/dev
cp ../backend.hcl.example backend.hcl           # values from `terraform output backend_config`
terraform init -backend-config=backend.hcl
export TF_VAR_subscription_id=<subscription id>
terraform plan -var-file=dev.tfvars -out=plan.tfplan
terraform apply plan.tfplan
```

API Management in internal virtual network mode takes 30 to 60 minutes to provision. That is
normal.

In CI use the **Deploy** workflow. It authenticates with workload identity federation (no
stored secrets), plans, and waits for an approval on the GitHub environment before it applies.

## 3. Add a model deployment

Check which models and quota your region offers, then add to the environment's tfvars:

```hcl
deployments = {
  chat = { model_name = "<model>", model_version = "<version>", sku_name = "GlobalStandard", capacity = 10 }
}
```

Callers use the gateway: `POST {gateway_url}/openai/deployments/chat/chat/completions` with an
Entra token for the gateway audience.

## 4. Promote dev to prod

Merge to `main`, run the Deploy workflow for `prod`. The code is the same, only the values
differ: `Premium_1` gateway, `Deny` policy effect, longer log retention.

## Operating it

| Situation | Action |
|---|---|
| A caller gets 429 | They exceeded `tokens_per_minute`. Raise it in tfvars for that environment, or give the caller a separate gateway product. |
| Policy blocks a deployment | The change reopens a control. Fix the change. If the exception is legitimate, record it with `tfpolicy:ignore` and a reason, and review it in the pull request. |
| Model quota exhausted | Add a second deployment in another region and route by deployment name at the gateway. |
| Region outage | Deploy the environment root in a second region (new `location`, new `address_space`), put both behind your global entry point. Premium API Management supports multi-region units. |
| Break glass | An Owner can remove a policy assignment. Do it in a pull request so it is reviewed, and expect the audit log to show it. |
| Rotating anything | There is nothing to rotate: no keys, no shared secrets. Tokens come from Entra ID and managed identities. |
| Destroying an environment | Remove the state lock (`protect-tfstate`) deliberately first. Key Vault purge protection keeps names reserved for 90 days. |

## Costs to watch

API Management Developer and Premium are billed hourly whether or not traffic flows. Log
Analytics ingestion grows with request volume, so set `daily_quota_gb` where it matters.
Model cost is per token and unaffected by this code, but the per-caller token limit is the
control that bounds it.

## Setting up the Deploy workflow (OIDC)

1. Create a Microsoft Entra app registration (or a user-assigned managed identity) for the pipeline.
2. Add federated credentials for the GitHub repository, one per environment the workflow uses.
   The subject is `repo:<owner>/<repo>:environment:<name>` for each of `dev-plan`, `dev`,
   `prod-plan` and `prod`.
3. Give the `-plan` identity read access on the subscription and `Storage Blob Data
   Contributor` on the state container (plans take a state lock). Give the apply identity
   what the modules create: Contributor, User Access Administrator and Resource Policy
   Contributor at subscription scope, or a narrower custom role you control.
4. In the repository settings, create the environments and add **required reviewers** to
   `dev` and `prod`. Add these as environment or repository *variables* (they are identifiers,
   not secrets): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
   `TFSTATE_RESOURCE_GROUP`, `TFSTATE_STORAGE_ACCOUNT`, `TFSTATE_CONTAINER`.
5. Run **Deploy** from the Actions tab. Leave *apply* unticked to review the plan first.

Run `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64` in each root once
and commit `.terraform.lock.hcl`, so provider checksums are pinned.
