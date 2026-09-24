variable "project_name" {
  type = string
}

variable "region" {
  type = string
}

variable "network_id" {
  type = string
}

variable "tier" {
  description = "Cloud SQL Enterprise machine type for the demo"
  type        = string
  default     = "db-custom-2-7680"
}

variable "availability_type" {
  description = "Cloud SQL availability"
  type        = string
  default     = "ZONAL"
}

variable "deletion_protection" {
  description = "Prevent accidental deletion"
  type        = bool
  default     = false
}