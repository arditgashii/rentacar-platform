variable "subscription_id" {
  description = "Azure subscription to deploy into."
  type        = string
}

variable "name" {
  description = "Short name used as a prefix for every resource (letters and digits only)."
  type        = string
  default     = "drivenow"

  validation {
    condition     = can(regex("^[a-z0-9]{3,12}$", var.name))
    error_message = "Use 3 to 12 lower-case letters or digits."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westeurope"
}

variable "sql_admin_login" {
  description = "Administrator login of the Azure SQL server."
  type        = string
  default     = "drivenowadmin"
}

variable "aks_node_count" {
  description = "Number of nodes in the AKS system pool."
  type        = number
  default     = 2
}

variable "aks_node_size" {
  description = "VM size of the AKS nodes."
  type        = string
  default     = "Standard_B2s"
}

variable "tags" {
  description = "Tags added to every resource."
  type        = map(string)
  default = {
    project = "drivenow"
    purpose = "qa-portfolio"
  }
}
