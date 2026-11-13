# Values for the prod environment. Replace the placeholders before planning.
# subscription_id is supplied by the pipeline as TF_VAR_subscription_id.

environment         = "prod"
location            = "swedencentral"
allowed_locations   = ["swedencentral", "westeurope"]
owner               = "platform-ai"
cost_center         = "CC-0000"
data_classification = "confidential"
address_space       = "10.41.0.0/16"
log_retention_days  = 180
caller_audience     = "api://ai-gateway"
publisher_name      = "Platform AI"
publisher_email     = "platform-ai@example.com"
apim_sku_name       = "Premium_1"
tokens_per_minute   = 60000
policy_effect       = "Deny"
deployments         = {}
