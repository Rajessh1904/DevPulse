variable "project_id" {
  type = string
}
variable "project_name" {
  type    = string
  default = "devpulse"
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "github_repo" {
  description = "e.g. your-org/devpulse"
  type        = string
}
