output "log_analytics_workspace_id" {
  description = "Id of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.this.id
}

output "application_insights_id" {
  description = "Id of the Application Insights component."
  value       = azurerm_application_insights.this.id
}

output "application_insights_instrumentation_key" {
  description = "Instrumentation key used by the API gateway logger."
  value       = azurerm_application_insights.this.instrumentation_key
  sensitive   = true
}
