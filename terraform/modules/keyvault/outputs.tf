output "id" {
  description = "Id of the key vault."
  value       = azurerm_key_vault.this.id
}

output "name" {
  description = "Name of the key vault."
  value       = azurerm_key_vault.this.name
}

output "vault_uri" {
  description = "Vault URI, resolvable only through the private endpoint."
  value       = azurerm_key_vault.this.vault_uri
}
