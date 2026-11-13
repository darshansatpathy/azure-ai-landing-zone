output "resource_group_name" {
  description = "Resource group of the environment."
  value       = azurerm_resource_group.this.name
}

output "gateway_url" {
  description = "Gateway URL, resolvable inside the virtual network."
  value       = module.ai_gateway.gateway_url
}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint, reachable only through the private endpoint."
  value       = module.openai.endpoint
}

output "key_vault_uri" {
  description = "Key Vault URI, reachable only through the private endpoint."
  value       = module.keyvault.vault_uri
}
