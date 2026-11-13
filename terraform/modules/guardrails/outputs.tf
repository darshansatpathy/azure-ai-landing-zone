output "definition_ids" {
  description = "Policy definition ids by name."
  value       = { for k, d in azurerm_policy_definition.this : k => d.id }
}

output "assignment_ids" {
  description = "Policy assignment ids by name."
  value       = { for k, a in azurerm_resource_group_policy_assignment.this : k => a.id }
}
