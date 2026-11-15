# tfpolicy:ignore TFP017 reason="Bootstrap creates the state backend, so its first run uses local state. The runbook migrates that state into the backend it creates."
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.13"
    }
  }
}

provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  features {}
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "state" {
  name     = "rg-${var.workload}-tfstate"
  location = var.location
  tags     = var.tags
}

# tfpolicy:ignore TFP008 reason="State backend is reached from CI runners over the public endpoint, restricted by firewall rules and Entra ID authentication. A private endpoint would need self-hosted runners."
resource "azurerm_storage_account" "state" {
  name                            = var.state_storage_account_name
  location                        = var.location
  resource_group_name             = azurerm_resource_group.state.name
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  https_traffic_only_enabled      = true
  tags                            = var.tags

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
    ip_rules       = var.allowed_ip_ranges
  }
}

resource "azurerm_storage_container" "state" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

resource "azurerm_role_assignment" "state_writer" {
  for_each = var.state_writer_principal_ids

  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
  principal_type       = var.state_writer_principal_type
}

resource "azurerm_management_lock" "state" {
  name       = "protect-tfstate"
  scope      = azurerm_storage_account.state.id
  lock_level = "CanNotDelete"
  notes      = "Holds Terraform state for the landing zone. Remove the lock deliberately before deleting."
}
