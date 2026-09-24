resource "google_sql_database_instance" "postgres" {
  name             = "${var.project_name}-sql"
  database_version = "POSTGRES_17"
  region           = var.region

  settings {
    tier              = var.tier
    edition           = "ENTERPRISE"
    availability_type = var.availability_type

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "02:00"
    }
  }

  deletion_protection = var.deletion_protection
}

resource "google_sql_database" "app_db" {
  name     = "devpulse"
  instance = google_sql_database_instance.postgres.name
}

resource "random_password" "db_password" {
  length  = 20
  special = false
}

resource "google_sql_user" "app_user" {
  name     = "devpulse"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db_password.result
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.project_name}-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}