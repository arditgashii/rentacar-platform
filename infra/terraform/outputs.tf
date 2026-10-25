output "resource_group" {
  value = azurerm_resource_group.main.name
}

output "key_vault_url" {
  value = azurerm_key_vault.main.vault_uri
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "aks_name" {
  value = azurerm_kubernetes_cluster.main.name
}

output "app_identity_client_id" {
  description = "Goes into serviceAccount.clientId of the Helm chart."
  value       = azurerm_user_assigned_identity.app.client_id
}

output "sql_server_fqdn" {
  value = azurerm_mssql_server.main.fully_qualified_domain_name
}

output "servicebus_namespace" {
  value = azurerm_servicebus_namespace.main.name
}
