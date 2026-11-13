variable "subscription_id" {
  type        = string
  description = "Subscription the environment is deployed into."
}

variable "workload" {
  type        = string
  description = "Workload name used in resource names."
  default     = "aiz"
}

variable "environment" {
  type        = string
  description = "Environment name."

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "allowed_locations" {
  type        = list(string)
  description = "Regions the policy allows resources in."
}

variable "owner" {
  type        = string
  description = "Team that owns the environment, used in the owner tag."
}

variable "cost_center" {
  type        = string
  description = "Cost center, used in the cost-center tag."
}

variable "data_classification" {
  type        = string
  description = "Highest data classification the environment may hold."

  validation {
    condition     = contains(["public", "internal", "confidential", "restricted"], var.data_classification)
    error_message = "data_classification must be public, internal, confidential or restricted."
  }
}

variable "address_space" {
  type        = string
  description = "CIDR block of the virtual network. A /16 leaves room for the three /24 subnets."
}

variable "log_retention_days" {
  type        = number
  description = "Log retention in days."
  default     = 90
}

variable "deployments" {
  type = map(object({
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
  description = "Model deployments keyed by deployment name."
  default     = {}
}

variable "caller_audience" {
  type        = string
  description = "Audience that caller tokens must carry at the gateway."
}

variable "publisher_name" {
  type        = string
  description = "Publisher name shown in the gateway."
}

variable "publisher_email" {
  type        = string
  description = "Contact address for gateway notifications."
}

variable "apim_sku_name" {
  type        = string
  description = "API Management SKU."
}

variable "tokens_per_minute" {
  type        = number
  description = "Token budget per calling identity per minute."
}

variable "policy_effect" {
  type        = string
  description = "Azure Policy effect: Deny blocks non-compliant changes, Audit only reports."
}
