terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

resource "azurerm_cognitive_account" "this" {
  name                          = "oai-${var.name_prefix}-${var.suffix}"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "oai-${var.name_prefix}-${var.suffix}"
  public_network_access_enabled = false
  local_auth_enabled            = false
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_deployment" "this" {
  for_each = var.deployments

  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.this.id
  rai_policy_name      = var.rai_policy_name

  model {
    format  = "OpenAI"
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity
  }
}

resource "azurerm_private_endpoint" "this" {
  name                = "pe-${azurerm_cognitive_account.this.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-openai"
    private_connection_resource_id = azurerm_cognitive_account.this.id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "openai"
    private_dns_zone_ids = var.private_dns_zone_ids
  }
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-openai"
  target_resource_id         = azurerm_cognitive_account.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
  }
}

resource "azurerm_role_assignment" "openai_user" {
  for_each = var.openai_user_principal_ids

  scope                = azurerm_cognitive_account.this.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = each.value
  principal_type       = "ServicePrincipal"
}
