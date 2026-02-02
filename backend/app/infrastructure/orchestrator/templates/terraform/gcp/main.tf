# Cerberus CTF - GCP Terraform Module
# Provisions Compute Engine instances for cloud exploitation challenges

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "instance_id" {
  description = "Unique challenge instance ID"
  type        = string
}

variable "user_id" {
  description = "User ID who owns this instance"
  type        = string
}

variable "team_id" {
  description = "Team ID (optional)"
  type        = string
  default     = ""
}

variable "canary_token" {
  description = "Canary token for anti-cheat"
  type        = string
  default     = ""
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "machine_type" {
  description = "Machine type"
  type        = string
  default     = "e2-micro"
}

variable "challenge_port" {
  description = "Port the challenge service runs on"
  type        = number
  default     = 80
}

# Locals
locals {
  instance_name = "cerberus-challenge-${var.instance_id}"
  labels = {
    managed_by   = "cerberus"
    instance_id  = var.instance_id
    user_id      = var.user_id
    team_id      = var.team_id
    canary_token = var.canary_token
  }
}

# VPC Network
resource "google_compute_network" "challenge" {
  name                    = "${local.instance_name}-network"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  labels = local.labels
}

resource "google_compute_subnetwork" "challenge" {
  name          = "${local.instance_name}-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.challenge.id

  labels = local.labels
}

# Firewall Rules
resource "google_compute_firewall" "challenge_ingress" {
  name    = "${local.instance_name}-ingress"
  network = google_compute_network.challenge.name

  allow {
    protocol = "tcp"
    ports    = [var.challenge_port, "22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["cerberus-challenge"]

  labels = local.labels
}

resource "google_compute_firewall" "challenge_egress" {
  name    = "${local.instance_name}-egress"
  network = google_compute_network.challenge.name
  direction = "EGRESS"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  allow {
    protocol = "udp"
    ports    = ["53"]
  }

  destination_ranges = ["0.0.0.0/0"]
  target_tags        = ["cerberus-challenge"]

  labels = local.labels
}

# Service Account
resource "google_service_account" "challenge" {
  account_id   = "cerberus-${substr(var.instance_id, 0, 20)}"
  display_name = "Cerberus Challenge Service Account"
  description  = "Service account for challenge instance ${var.instance_id}"

  labels = local.labels
}

resource "google_project_iam_member" "challenge_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.challenge.email}"
}

# Compute Instance
resource "google_compute_instance" "challenge" {
  name         = local.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  tags = ["cerberus-challenge"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 20
      type  = "pd-standard"
    }

    auto_delete = true
  }

  network_interface {
    subnetwork = google_compute_subnetwork.challenge.id

    access_config {
      # Ephemeral public IP
    }
  }

  metadata = {
    canary-token = var.canary_token
    user-id      = var.user_id
    team-id      = var.team_id
    startup-script = <<-EOF
      #!/bin/bash
      set -e
      
      # Update system
      apt-get update
      apt-get install -y docker.io docker-compose
      
      # Setup canary
      echo "CERBERUS_CANARY=${var.canary_token}" >> /etc/environment
      
      # Pull and run challenge
      docker pull gcr.io/${var.project_id}/challenge:${var.instance_id}
      docker run -d \
        -p ${var.challenge_port}:${var.challenge_port} \
        -e CERBERUS_CANARY=${var.canary_token} \
        --name challenge \
        gcr.io/${var.project_id}/challenge:${var.instance_id}
      
      # Auto-terminate after 2 hours
      echo "shutdown -h +120" | at now
      
      # Signal completion
      echo "Challenge ready" > /var/log/challenge-setup.log
      EOF
  }

  service_account {
    email  = google_service_account.challenge.email
    scopes = ["cloud-platform"]
  }

  labels = local.labels

  # Prevent accidental deletion
  deletion_protection = false
}

# Static IP (optional)
resource "google_compute_address" "challenge" {
  name   = "${local.instance_name}-ip"
  region = var.region

  labels = local.labels
}

# Cloud Logging
resource "google_logging_project_sink" "challenge" {
  name        = "${local.instance_name}-logs"
  destination = "bigquery.googleapis.com/projects/${var.project_id}/datasets/cerberus_logs"
  filter      = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${google_compute_instance.challenge.id}\""

  unique_writer_identity = true
}

# Monitoring Alert
resource "google_monitoring_alert_policy" "challenge_uptime" {
  display_name = "${local.instance_name} Uptime"
  combiner     = "OR"

  conditions {
    display_name = "Instance Down"

    condition_threshold {
      filter          = "metric.type=\"compute.googleapis.com/instance/uptime\" AND resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${google_compute_instance.challenge.id}\""
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []
  severity              = "WARNING"

  labels = local.labels
}

# Outputs
output "instance_id" {
  description = "Compute instance ID"
  value       = google_compute_instance.challenge.id
}

output "instance_name" {
  description = "Instance name"
  value       = google_compute_instance.challenge.name
}

output "public_ip" {
  description = "Public IP address"
  value       = google_compute_instance.challenge.network_interface[0].access_config[0].nat_ip
}

output "private_ip" {
  description = "Private IP address"
  value       = google_compute_instance.challenge.network_interface[0].network_ip
}

output "access_url" {
  description = "URL to access the challenge"
  value       = "http://${google_compute_instance.challenge.network_interface[0].access_config[0].nat_ip}:${var.challenge_port}"
}

output "network_id" {
  description = "VPC network ID"
  value       = google_compute_network.challenge.id
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.challenge.email
}