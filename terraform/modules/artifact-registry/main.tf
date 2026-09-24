resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "${var.project_name}-images"
  description   = "Container images for DevPulse"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-last-10"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
}
