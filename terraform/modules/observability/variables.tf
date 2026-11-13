variable "name_prefix" {
  type        = string
  description = "Short prefix used in resource names."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group that holds the workspace."
}

variable "retention_in_days" {
  type        = number
  description = "Log retention in days. Audit evidence usually needs at least 90."
  default     = 90

  validation {
    condition     = var.retention_in_days >= 30 && var.retention_in_days <= 730
    error_message = "retention_in_days must be between 30 and 730."
  }
}

variable "daily_quota_gb" {
  type        = number
  description = "Daily ingestion cap in GB. Use -1 for no cap."
  default     = -1
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource."
}
