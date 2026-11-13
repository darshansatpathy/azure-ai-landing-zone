# Values for the dev environment. Replace the placeholders before planning.
# subscription_id is supplied by the pipeline as TF_VAR_subscription_id.

environment         = "dev"
location            = "swedencentral"
allowed_locations   = ["swedencentral", "westeurope"]
owner               = "platform-ai"
cost_center         = "CC-0000"
data_classification = "internal"
address_space       = "10.40.0.0/16"
log_retention_days  = 30
caller_audience     = "api://ai-gateway-dev"
publisher_name      = "Platform AI"
publisher_email     = "platform-ai@example.com"
apim_sku_name       = "Developer_1"
tokens_per_minute   = 20000
policy_effect       = "Audit"

# Deployments depend on the models and quota your region offers. Example:
# deployments = {
#   chat = { model_name = "gpt-4o-mini", model_version = "2024-07-18", sku_name = "GlobalStandard", capacity = 10 }
# }
deployments = {}
