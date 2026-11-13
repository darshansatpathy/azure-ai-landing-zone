variable "name_prefix" {
  type        = string
  description = "Short prefix used in resource names."
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
  description = "Resource group that holds the account."
}

variable "private_endpoint_subnet_id" {
  type        = string
  description = "Subnet for the private endpoint."
}

variable "private_dns_zone_ids" {
  type        = list(string)
  description = "Ids of the privatelink zones for OpenAI, Cognitive Services and AI Services."
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Workspace that receives request and audit logs."
}

variable "deployments" {
  type = map(object({
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
  description = "Model deployments keyed by deployment name. Check the model catalog for what your region offers."
  default     = {}
}

variable "rai_policy_name" {
  type        = string
  description = "Content filter policy applied to every deployment."
  default     = "Microsoft.DefaultV2"
}

variable "openai_user_principal_ids" {
  type        = map(string)
  description = "Identities granted Cognitive Services OpenAI User, keyed by a stable label."
  default     = {}
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource."
}
