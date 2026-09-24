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
  type    = string
  default = "db-custom-1-3840"
}
variable "availability_type" {
  type    = string
  default = "ZONAL"
}
variable "deletion_protection" {
  type    = bool
  default = true
}
