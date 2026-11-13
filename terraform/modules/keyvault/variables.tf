variable "name_prefix" {
  type        = string
  description = "Short prefix used in the vault name."
}

variable "suffix" {
  type        = string
  description = "Short deterministic suffix that makes the globally unique name unique."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group that holds the vault."
}

variable "tenant_id" {
  type        = string
  description = "Microsoft Entra tenant id."
}

variable "private_endpoint_subnet_id" {
  type        = string
  description = "Subnet for the private endpoint."
}

variable "private_dns_zone_id" {
  type        = string
  description = "Id of the privatelink.vaultcore.azure.net zone."
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Workspace that receives audit logs."
}

variable "secrets_user_principal_ids" {
  type        = map(string)
  description = "Identities allowed to read secrets, keyed by a stable label."
  default     = {}
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource."
}
