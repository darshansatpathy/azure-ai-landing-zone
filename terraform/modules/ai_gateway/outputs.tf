output "gateway_name" {
  description = "Name of the API Management instance."
  value       = azurerm_api_management.this.name
}

output "gateway_private_ip" {
  description = "Private IP addresses of the gateway."
  value       = azurerm_api_management.this.private_ip_addresses
}

output "gateway_url" {
  description = "Gateway URL, resolvable inside the virtual network."
  value       = azurerm_api_management.this.gateway_url
}
