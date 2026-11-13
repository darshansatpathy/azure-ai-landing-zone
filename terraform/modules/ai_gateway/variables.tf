variable "name_prefix" {
  type        = string
  description = "Short prefix used in resource names."
}

variable "suffix" {
  type        = string
  description = "Short deterministic suffix that makes globally unique names unique."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group that holds the gateway."
}

variable "tenant_id" {
  type        = string
  description = "Microsoft Entra tenant id that issues caller tokens."
}

variable "caller_audience" {
  type        = string
  description = "Audience that caller tokens must carry, for example api://ai-gateway."
}

variable "publisher_name" {
  type        = string
  description = "Publisher name shown in the gateway."
}

variable "publisher_email" {
  type        = string
  description = "Contact address for gateway notifications."
}

variable "sku_name" {
  type        = string
  description = "API Management SKU. Virtual network injection needs Developer or Premium."
  default     = "Developer_1"

  validation {
    condition     = can(regex("^(Developer|Premium)_[0-9]+$", var.sku_name))
    error_message = "sku_name must be Developer_N or Premium_N for virtual network injection."
  }
}

variable "tokens_per_minute" {
  type        = number
  description = "Token budget per calling identity per minute."
  default     = 20000

  validation {
    condition     = var.tokens_per_minute > 0
    error_message = "tokens_per_minute must be positive."
  }
}

variable "subnet_id" {
  type        = string
  description = "Subnet the gateway is injected into."
}

variable "virtual_network_id" {
  type        = string
  description = "Virtual network that resolves the private gateway name."
}

variable "network_security_group_name" {
  type        = string
  description = "Name of the network security group on the gateway subnet."
}

variable "gateway_identity_id" {
  type        = string
  description = "Resource id of the user-assigned identity the gateway runs as."
}

variable "gateway_identity_client_id" {
  type        = string
  description = "Client id of that identity, used to request model tokens."
}

variable "openai_endpoint" {
  type        = string
  description = "Endpoint of the Azure OpenAI account, with a trailing slash."
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Workspace that receives gateway logs."
}

variable "application_insights_id" {
  type        = string
  description = "Application Insights component used for the gateway logger."
}

variable "application_insights_instrumentation_key" {
  type        = string
  description = "Instrumentation key of that component."
  sensitive   = true
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource."
}
