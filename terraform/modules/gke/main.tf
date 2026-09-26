resource "google_container_cluster" "primary" {
  name            = "${var.project_name}-gke"
  location        = var.region
  enable_autopilot = true

  network    = var.network_id
  subnetwork = var.subnet_id

  resource_labels = {
    environment = "dev"
    application = "devpulse"
    managed_by  = "terraform"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "gke-pods"
    services_secondary_range_name = "gke-services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.master_authorized_cidr
      display_name = "Admin Network"
    }
  }

  release_channel {
    channel = "REGULAR"
  }

  deletion_protection = false

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

