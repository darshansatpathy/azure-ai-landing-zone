data "azurerm_client_config" "current" {}

locals {
  name_prefix = "${var.workload}-${var.environment}"
  suffix      = substr(sha1("${var.workload}-${var.environment}-${var.subscription_id}"), 0, 5)

  tags = {
    environment         = var.environment
    owner               = var.owner
    cost-center         = var.cost_center
    data-classification = var.data_classification
    managed-by          = "terraform"
  }

  private_dns_zones = toset([
    "privatelink.openai.azure.com",
    "privatelink.cognitiveservices.azure.com",
    "privatelink.services.ai.azure.com",
    "privatelink.vaultcore.azure.net",
  ])

  subnets = {
    private-endpoints = {
      address_prefixes                  = [cidrsubnet(var.address_space, 8, 0)]
      private_endpoint_network_policies = "NetworkSecurityGroupEnabled"
    }
    apim = {
      address_prefixes                  = [cidrsubnet(var.address_space, 8, 1)]
      private_endpoint_network_policies = "Disabled"
    }
    workload = {
      address_prefixes                  = [cidrsubnet(var.address_space, 8, 2)]
      private_endpoint_network_policies = "Disabled"
    }
  }
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_user_assigned_identity" "gateway" {
  name                = "id-${local.name_prefix}-gateway"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

module "network" {
  source = "../../modules/network"

  name_prefix         = local.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = var.address_space
  subnets             = local.subnets
  private_dns_zones   = local.private_dns_zones
  tags                = local.tags
}

module "observability" {
  source = "../../modules/observability"

  name_prefix         = local.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  retention_in_days   = var.log_retention_days
  tags                = local.tags
}

module "keyvault" {
  source = "../../modules/keyvault"

  name_prefix                = local.name_prefix
  suffix                     = local.suffix
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  private_endpoint_subnet_id = module.network.subnet_ids["private-endpoints"]
  private_dns_zone_id        = module.network.private_dns_zone_ids["privatelink.vaultcore.azure.net"]
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id
  tags                       = local.tags
}

module "openai" {
  source = "../../modules/openai"

  name_prefix                = local.name_prefix
  suffix                     = local.suffix
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  private_endpoint_subnet_id = module.network.subnet_ids["private-endpoints"]
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id
  deployments                = var.deployments
  tags                       = local.tags

  private_dns_zone_ids = [
    module.network.private_dns_zone_ids["privatelink.openai.azure.com"],
    module.network.private_dns_zone_ids["privatelink.cognitiveservices.azure.com"],
    module.network.private_dns_zone_ids["privatelink.services.ai.azure.com"],
  ]

  openai_user_principal_ids = {
    gateway = azurerm_user_assigned_identity.gateway.principal_id
  }
}

module "ai_gateway" {
  source = "../../modules/ai_gateway"

  name_prefix                              = local.name_prefix
  suffix                                   = local.suffix
  location                                 = var.location
  resource_group_name                      = azurerm_resource_group.this.name
  tenant_id                                = data.azurerm_client_config.current.tenant_id
  caller_audience                          = var.caller_audience
  publisher_name                           = var.publisher_name
  publisher_email                          = var.publisher_email
  sku_name                                 = var.apim_sku_name
  tokens_per_minute                        = var.tokens_per_minute
  subnet_id                                = module.network.subnet_ids["apim"]
  virtual_network_id                       = module.network.virtual_network_id
  network_security_group_name              = module.network.nsg_names["apim"]
  gateway_identity_id                      = azurerm_user_assigned_identity.gateway.id
  gateway_identity_client_id               = azurerm_user_assigned_identity.gateway.client_id
  openai_endpoint                          = module.openai.endpoint
  log_analytics_workspace_id               = module.observability.log_analytics_workspace_id
  application_insights_id                  = module.observability.application_insights_id
  application_insights_instrumentation_key = module.observability.application_insights_instrumentation_key
  tags                                     = local.tags
}

module "guardrails" {
  source = "../../modules/guardrails"

  resource_group_id = azurerm_resource_group.this.id
  effect            = var.policy_effect
  allowed_locations = var.allowed_locations
  required_tags     = ["environment", "owner", "cost-center", "data-classification"]
}
