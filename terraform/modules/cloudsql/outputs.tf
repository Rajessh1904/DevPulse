output "instance_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}
output "private_ip" {
  value = google_sql_database_instance.postgres.private_ip_address
}
output "secret_id" {
  value = google_secret_manager_secret.db_password.secret_id
}
