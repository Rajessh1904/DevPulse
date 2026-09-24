output "repository_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_name}/${google_artifact_registry_repository.repo.repository_id}"
}
