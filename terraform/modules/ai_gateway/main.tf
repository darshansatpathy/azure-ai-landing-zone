terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

resource "azurerm_public_ip" "this" {
  name                = "pip-${var.name_prefix}-apim"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "apim-${var.name_prefix}-${var.suffix}"
  tags                = var.tags
}

resource "azurerm_api_management" "this" {
  name                 = "apim-${var.name_prefix}-${var.suffix}"
  location             = var.location
  resource_group_name  = var.resource_group_name
  publisher_name       = var.publisher_name
  publisher_email      = var.publisher_email
  sku_name             = var.sku_name
  virtual_network_type = "Internal"
  public_ip_address_id = azurerm_public_ip.this.id
  tags                 = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.gateway_identity_id]
  }

  virtual_network_configuration {
    subnet_id = var.subnet_id
  }
}

resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-apim"
  target_resource_id         = azurerm_api_management.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
  }
}

resource "azurerm_api_management_logger" "this" {
  name                = "appinsights"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  resource_id         = var.application_insights_id

  application_insights {
    instrumentation_key = var.application_insights_instrumentation_key
  }
}

resource "azurerm_api_management_api" "openai" {
  name                  = "azure-openai"
  resource_group_name   = var.resource_group_name
  api_management_name   = azurerm_api_management.this.name
  revision              = "1"
  display_name          = "Azure OpenAI"
  path                  = "openai"
  protocols             = ["https"]
  service_url           = "${var.openai_endpoint}openai"
  subscription_required = false
}

resource "azurerm_api_management_api_operation" "chat" {
  operation_id        = "chat-completions"
  api_name            = azurerm_api_management_api.openai.name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  display_name        = "Chat completions"
  method              = "POST"
  url_template        = "/deployments/{deployment-id}/chat/completions"

  template_parameter {
    name     = "deployment-id"
    required = true
    type     = "string"
  }

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_policy" "openai" {
  api_name            = azurerm_api_management_api.openai.name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name

  xml_content = templatefile("${path.module}/policies/openai-gateway.xml.tftpl", {
    tenant_id         = var.tenant_id
    audience          = var.caller_audience
    tokens_per_minute = var.tokens_per_minute
    gateway_client_id = var.gateway_identity_client_id
  })
}

resource "azurerm_api_management_diagnostic" "this" {
  identifier               = "applicationinsights"
  resource_group_name      = var.resource_group_name
  api_management_name      = azurerm_api_management.this.name
  api_management_logger_id = azurerm_api_management_logger.this.id
  sampling_percentage      = 100
  always_log_errors        = true
  log_client_ip            = false
  verbosity                = "information"
}

resource "azurerm_private_dns_zone" "apim" {
  name                = "azure-api.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "apim" {
  name                  = "link-azure-api-net"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.apim.name
  virtual_network_id    = var.virtual_network_id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_private_dns_a_record" "gateway" {
  name                = azurerm_api_management.this.name
  zone_name           = azurerm_private_dns_zone.apim.name
  resource_group_name = var.resource_group_name
  ttl                 = 300
  records             = azurerm_api_management.this.private_ip_addresses
}

resource "azurerm_network_security_rule" "in_management" {
  name                        = "allow-apim-management"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "3443"
  source_address_prefix       = "ApiManagement"
  destination_address_prefix  = "VirtualNetwork"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "in_load_balancer" {
  name                        = "allow-azure-load-balancer"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "6390"
  source_address_prefix       = "AzureLoadBalancer"
  destination_address_prefix  = "VirtualNetwork"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "in_clients" {
  name                        = "allow-clients-https"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "VirtualNetwork"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "out_storage" {
  name                        = "allow-storage"
  priority                    = 100
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "Storage"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "out_sql" {
  name                        = "allow-sql"
  priority                    = 110
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "1433"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "Sql"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "out_entra" {
  name                        = "allow-entra-id"
  priority                    = 120
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "AzureActiveDirectory"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "out_key_vault" {
  name                        = "allow-key-vault"
  priority                    = 130
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "AzureKeyVault"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "out_monitor" {
  name                        = "allow-azure-monitor"
  priority                    = 140
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_ranges     = ["443", "1886"]
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "AzureMonitor"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}

resource "azurerm_network_security_rule" "out_model" {
  name                        = "allow-model-private-endpoint"
  priority                    = 150
  direction                   = "Outbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "VirtualNetwork"
  resource_group_name         = var.resource_group_name
  network_security_group_name = var.network_security_group_name
}
