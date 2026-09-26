variable "project_id" {
  type = string
}
variable "project_name" {
  type = string
}
variable "region" {
  type = string
}
variable "network_id" {
  type = string
}
variable "subnet_id" {
  type = string
}
variable "master_authorized_cidr" {
  description = "CIDR range allowed to access the GKE control plane"
  type        = string
}