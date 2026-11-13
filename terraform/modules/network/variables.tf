variable "name_prefix" {
  type        = string
  description = "Short prefix used in resource names, for example aiz-dev."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group that holds the network."
}

variable "address_space" {
  type        = string
  description = "CIDR block of the virtual network."

  validation {
    condition     = can(cidrnetmask(var.address_space))
    error_message = "address_space must be a valid IPv4 CIDR block."
  }
}

variable "subnets" {
  type = map(object({
    address_prefixes                  = list(string)
    private_endpoint_network_policies = string
  }))
  description = "Subnets to create. Every subnet gets its own network security group."
}

variable "private_dns_zones" {
  type        = set(string)
  description = "Private DNS zones to create and link to the virtual network."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource."
}
