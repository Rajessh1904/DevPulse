terraform {
  required_version = ">= 1.9"

  required_providers {
    # google provider v8.x is current as of writing.
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Create this bucket manually once, with versioning enabled, before first init:
  #   gsutil mb -l <region> gs://<project_id>-tfstate
  #   gsutil versioning set on gs://<project_id>-tfstate
  backend "gcs" {
    bucket = "REPLACE_WITH_YOUR_TFSTATE_BUCKET"
    prefix = "devpulse/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
