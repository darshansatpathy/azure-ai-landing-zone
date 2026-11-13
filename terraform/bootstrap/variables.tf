variable "subscription_id" {
  type        = string
  description = "Subscription that holds the state storage."
}

variable "workload" {
  type        = string
  description = "Workload name used in resource names."
  default     = "aiz"
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "state_storage_account_name" {
  type        = string
  description = "Globally unique storage account name, 3 to 24 lowercase letters and digits."

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.state_storage_account_name))
    error_message = "state_storage_account_name must be 3 to 24 lowercase letters and digits."
  }
}

variable "allowed_ip_ranges" {
  type        = list(string)
  description = "Public IP ranges allowed to reach the state storage, for example CI runner egress."
  default     = []
}

variable "state_writer_principal_ids" {
  type        = map(string)
  description = "Identities allowed to read and write state, keyed by a stable label."
}

variable "state_writer_principal_type" {
  type        = string
  description = "Principal type of the state writers: ServicePrincipal, User or Group."
  default     = "ServicePrincipal"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource."
}
