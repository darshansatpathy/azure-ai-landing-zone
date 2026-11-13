output "virtual_network_id" {
  description = "Id of the virtual network."
  value       = azurerm_virtual_network.this.id
}

output "subnet_ids" {
  description = "Subnet ids by subnet key."
  value       = { for k, s in azurerm_subnet.this : k => s.id }
}

output "nsg_names" {
  description = "Network security group names by subnet key."
  value       = { for k, n in azurerm_network_security_group.this : k => n.name }
}

output "private_dns_zone_ids" {
  description = "Private DNS zone ids by zone name."
  value       = { for k, z in azurerm_private_dns_zone.this : k => z.id }
}

output "virtual_network_name" {
  description = "Name of the virtual network."
  value       = azurerm_virtual_network.this.name
}
