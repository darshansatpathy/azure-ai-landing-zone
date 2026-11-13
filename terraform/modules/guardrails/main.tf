terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

locals {
  effect_parameter = {
    effect = {
      type          = "String"
      allowedValues = ["Audit", "Deny", "Disabled"]
      defaultValue  = "Deny"
      metadata      = { displayName = "Effect" }
    }
  }

  definitions = {
    "deny-ai-public-network" = {
      display_name = "AI landing zone: Cognitive Services accounts must not allow public network access"
      description  = "Denies Azure OpenAI and other Cognitive Services accounts that accept traffic from the public internet."
      parameters   = jsonencode(local.effect_parameter)
      rule = jsonencode({
        if = {
          allOf = [
            { field = "type", equals = "Microsoft.CognitiveServices/accounts" },
            { field = "Microsoft.CognitiveServices/accounts/publicNetworkAccess", notEquals = "Disabled" },
          ]
        }
        then = { effect = "[parameters('effect')]" }
      })
    }
    "deny-ai-local-auth" = {
      display_name = "AI landing zone: Cognitive Services accounts must disable key authentication"
      description  = "Denies accounts that still allow API keys, so every caller authenticates with Microsoft Entra ID."
      parameters   = jsonencode(local.effect_parameter)
      rule = jsonencode({
        if = {
          allOf = [
            { field = "type", equals = "Microsoft.CognitiveServices/accounts" },
            { field = "Microsoft.CognitiveServices/accounts/disableLocalAuth", notEquals = true },
          ]
        }
        then = { effect = "[parameters('effect')]" }
      })
    }
    "deny-keyvault-no-purge-protection" = {
      display_name = "AI landing zone: Key Vaults must have purge protection"
      description  = "Denies key vaults without purge protection so keys cannot be destroyed permanently by mistake."
      parameters   = jsonencode(local.effect_parameter)
      rule = jsonencode({
        if = {
          allOf = [
            { field = "type", equals = "Microsoft.KeyVault/vaults" },
            { field = "Microsoft.KeyVault/vaults/enablePurgeProtection", notEquals = true },
          ]
        }
        then = { effect = "[parameters('effect')]" }
      })
    }
    "require-tag" = {
      display_name = "AI landing zone: resources must carry a required tag"
      description  = "Denies resources that are missing the tag named by the tagName parameter."
      parameters = jsonencode(merge(local.effect_parameter, {
        tagName = { type = "String", metadata = { displayName = "Tag name" } }
      }))
      rule = jsonencode({
        if = {
          field  = "[concat('tags[', parameters('tagName'), ']')]"
          exists = false
        }
        then = { effect = "[parameters('effect')]" }
      })
    }
    "allowed-locations" = {
      display_name = "AI landing zone: resources must be in an approved region"
      description  = "Denies resources outside the approved regions, for data residency."
      parameters = jsonencode(merge(local.effect_parameter, {
        allowedLocations = { type = "Array", metadata = { displayName = "Allowed locations" } }
      }))
      rule = jsonencode({
        if = {
          allOf = [
            { field = "location", notIn = "[parameters('allowedLocations')]" },
            { field = "location", notEquals = "global" },
          ]
        }
        then = { effect = "[parameters('effect')]" }
      })
    }
  }

  assignments = merge(
    {
      "deny-ai-public-network"            = { definition = "deny-ai-public-network", parameters = { effect = { value = var.effect } } }
      "deny-ai-local-auth"                = { definition = "deny-ai-local-auth", parameters = { effect = { value = var.effect } } }
      "deny-keyvault-no-purge-protection" = { definition = "deny-keyvault-no-purge-protection", parameters = { effect = { value = var.effect } } }
      "allowed-locations" = {
        definition = "allowed-locations"
        parameters = { effect = { value = var.effect }, allowedLocations = { value = var.allowed_locations } }
      }
    },
    {
      for tag in var.required_tags : "require-tag-${tag}" => {
        definition = "require-tag"
        parameters = { effect = { value = var.effect }, tagName = { value = tag } }
      }
    }
  )
}

resource "azurerm_policy_definition" "this" {
  for_each = local.definitions

  name         = each.key
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = each.value.display_name
  description  = each.value.description
  metadata     = jsonencode({ category = "AI Landing Zone", version = "1.0.0" })
  parameters   = each.value.parameters
  policy_rule  = each.value.rule
}

resource "azurerm_resource_group_policy_assignment" "this" {
  for_each = local.assignments

  name                 = substr(each.key, 0, 64)
  resource_group_id    = var.resource_group_id
  policy_definition_id = azurerm_policy_definition.this[each.value.definition].id
  display_name         = each.key
  parameters           = jsonencode(each.value.parameters)
}
