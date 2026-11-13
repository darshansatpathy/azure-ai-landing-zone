output "id" {
  description = "Id of the Azure OpenAI account."
  value       = azurerm_cognitive_account.this.id
}

output "name" {
  description = "Name of the Azure OpenAI account."
  value       = azurerm_cognitive_account.this.name
}

output "endpoint" {
  description = "Endpoint of the account, resolvable only through the private endpoint."
  value       = azurerm_cognitive_account.this.endpoint
}

output "deployment_names" {
  description = "Names of the model deployments."
  value       = keys(azurerm_cognitive_deployment.this)
}
