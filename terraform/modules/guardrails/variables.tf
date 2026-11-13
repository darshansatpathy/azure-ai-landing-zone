variable "resource_group_id" {
  type        = string
  description = "Resource group the policies are assigned to."
}

variable "effect" {
  type        = string
  description = "Policy effect: Deny blocks non-compliant changes, Audit only reports them."
  default     = "Deny"

  validation {
    condition     = contains(["Audit", "Deny", "Disabled"], var.effect)
    error_message = "effect must be Audit, Deny or Disabled."
  }
}

variable "allowed_locations" {
  type        = list(string)
  description = "Regions resources may be created in."
}

variable "required_tags" {
  type        = list(string)
  description = "Tags every resource must carry."
}
