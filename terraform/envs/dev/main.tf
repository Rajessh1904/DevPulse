module "vpc" {
  source       = "../../modules/vpc"
  project_name = var.project_name
  region       = var.region
}

module "artifact_registry" {
  source       = "../../modules/artifact-registry"
  project_name = var.project_name
  region       = var.region
}

module "gke" {
  source       = "../../modules/gke"
  project_id   = var.project_id
  project_name = var.project_name
  region       = var.region
  network_id   = module.vpc.network_id
  subnet_id    = module.vpc.subnet_id
}

module "cloudsql" {
  source       = "../../modules/cloudsql"
  project_name = var.project_name
  region       = var.region
  network_id   = module.vpc.network_id

  depends_on = [module.vpc]
}

module "iam_wif" {
  source       = "../../modules/iam-wif"
  project_id   = var.project_id
  project_name = var.project_name
  github_repo  = var.github_repo
}
