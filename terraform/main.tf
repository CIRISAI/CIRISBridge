# CIRISBridge Infrastructure
# Terraform configuration for active/active multi-region deployment
#
# This provisions:
# - Vultr VPS (US) - Active node serving Americas
# - Hetzner VPS (EU) - Active node serving Europe
#
# Both nodes are equal peers with bi-directional PostgreSQL replication.
# GeoDNS routes users to the nearest region.
#
# Usage:
#   cd terraform
#   terraform init
#   terraform plan -out=tfplan
#   terraform apply tfplan

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    vultr = {
      source  = "vultr/vultr"
      version = "~> 2.19"
    }
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
  }

  # Optional: Configure remote state backend
  # backend "s3" {
  #   bucket = "cirisbridge-tfstate"
  #   key    = "terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# =============================================================================
# Providers
# =============================================================================

provider "vultr" {
  api_key     = var.vultr_api_key
  rate_limit  = 100
  retry_limit = 3
}

provider "hcloud" {
  token = var.hetzner_api_token
}

# =============================================================================
# Data Sources
# =============================================================================

# Get Vultr OS ID for Ubuntu 22.04
data "vultr_os" "ubuntu" {
  filter {
    name   = "name"
    values = ["Ubuntu 22.04 LTS x64"]
  }
}

# =============================================================================
# SSH Keys
# =============================================================================

resource "vultr_ssh_key" "cirisbridge" {
  name    = "cirisbridge-deploy"
  ssh_key = var.ssh_public_key
}

resource "hcloud_ssh_key" "cirisbridge" {
  name       = "cirisbridge-deploy"
  public_key = var.ssh_public_key
}

# =============================================================================
# Firewall Rules
# =============================================================================

resource "vultr_firewall_group" "cirisbridge" {
  description = "CIRISBridge firewall rules"
}

resource "vultr_firewall_rule" "ssh" {
  firewall_group_id = vultr_firewall_group.cirisbridge.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = var.admin_ip
  subnet_size       = 32
  port              = "22"
  notes             = "SSH from admin"
}

resource "vultr_firewall_rule" "dns_udp" {
  firewall_group_id = vultr_firewall_group.cirisbridge.id
  protocol          = "udp"
  ip_type           = "v4"
  subnet            = "0.0.0.0"
  subnet_size       = 0
  port              = "53"
  notes             = "DNS UDP"
}

resource "vultr_firewall_rule" "dns_tcp" {
  firewall_group_id = vultr_firewall_group.cirisbridge.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "0.0.0.0"
  subnet_size       = 0
  port              = "53"
  notes             = "DNS TCP"
}

resource "vultr_firewall_rule" "https" {
  firewall_group_id = vultr_firewall_group.cirisbridge.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "0.0.0.0"
  subnet_size       = 0
  port              = "443"
  notes             = "HTTPS"
}

resource "vultr_firewall_rule" "http" {
  firewall_group_id = vultr_firewall_group.cirisbridge.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "0.0.0.0"
  subnet_size       = 0
  port              = "80"
  notes             = "HTTP (for ACME challenges)"
}

# Hetzner firewall
resource "hcloud_firewall" "cirisbridge" {
  name = "cirisbridge"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.admin_ip}/32"]
  }

  rule {
    direction  = "in"
    protocol   = "udp"
    port       = "53"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "53"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}

# =============================================================================
# Compute Instances
# =============================================================================

# Vultr instance (US - Active node)
resource "vultr_instance" "us" {
  plan              = var.vultr_plan
  region            = var.vultr_region
  os_id             = data.vultr_os.ubuntu.id
  label             = "cirisbridge-us"
  hostname          = "cirisbridge-us"
  enable_ipv6       = true
  backups           = "disabled"  # Manual backups to reduce cost
  ddos_protection   = false
  activation_email  = false
  ssh_key_ids       = [vultr_ssh_key.cirisbridge.id]
  firewall_group_id = vultr_firewall_group.cirisbridge.id

  tags = ["cirisbridge", "active", "us"]
}

# Hetzner instance (EU - Active node)
resource "hcloud_server" "eu" {
  name        = "cirisbridge-eu"
  server_type = var.hetzner_server_type
  location    = var.hetzner_location
  image       = "ubuntu-22.04"
  ssh_keys    = [hcloud_ssh_key.cirisbridge.id]
  firewall_ids = [hcloud_firewall.cirisbridge.id]

  labels = {
    environment = "production"
    role        = "active"
    region      = "eu"
  }
}

# Hetzner block storage for PostgreSQL
resource "hcloud_volume" "postgres_eu" {
  name      = "postgres-eu"
  size      = var.hetzner_volume_size
  location  = var.hetzner_location
  format    = "ext4"
}

resource "hcloud_volume_attachment" "postgres_eu" {
  volume_id = hcloud_volume.postgres_eu.id
  server_id = hcloud_server.eu.id
  automount = true
}

# =============================================================================
# Inter-region Firewall Rules (Bi-directional for Active/Active)
# =============================================================================

# Allow PostgreSQL bi-directional replication: EU -> US
resource "vultr_firewall_rule" "postgres_from_eu" {
  firewall_group_id = vultr_firewall_group.cirisbridge.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = hcloud_server.eu.ipv4_address
  subnet_size       = 32
  port              = "5432"
  notes             = "PostgreSQL bi-directional replication from EU"
}

# Allow PostgreSQL bi-directional replication: US -> EU
resource "hcloud_firewall" "postgres_from_us" {
  name = "cirisbridge-postgres"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "5432"
    source_ips = ["${vultr_instance.us.main_ip}/32"]
  }
}

# Attach postgres firewall to EU server
resource "hcloud_firewall_attachment" "postgres_eu" {
  firewall_id = hcloud_firewall.postgres_from_us.id
  server_ids  = [hcloud_server.eu.id]
}

# =============================================================================
# Test Environment (Optional - enabled via create_test_env variable)
# Full stack: postgres+lens, billing+proxy, manager+scout
# =============================================================================

# Test VPC - isolated network for all test services
resource "vultr_vpc2" "test" {
  count          = var.create_test_env ? 1 : 0
  description    = "CIRIS Test Environment VPC"
  region         = var.vultr_region
  ip_block       = "10.0.0.0"
  prefix_length  = 24
}

# Test Firewall - SSH from admin, HTTP/HTTPS public
resource "vultr_firewall_group" "test" {
  count       = var.create_test_env ? 1 : 0
  description = "CIRIS Test Environment Firewall"
}

resource "vultr_firewall_rule" "test_ssh" {
  count             = var.create_test_env ? 1 : 0
  firewall_group_id = vultr_firewall_group.test[0].id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = var.admin_ip
  subnet_size       = 32
  port              = "22"
  notes             = "SSH from admin"
}

resource "vultr_firewall_rule" "test_https" {
  count             = var.create_test_env ? 1 : 0
  firewall_group_id = vultr_firewall_group.test[0].id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "0.0.0.0"
  subnet_size       = 0
  port              = "443"
  notes             = "HTTPS"
}

resource "vultr_firewall_rule" "test_http" {
  count             = var.create_test_env ? 1 : 0
  firewall_group_id = vultr_firewall_group.test[0].id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "0.0.0.0"
  subnet_size       = 0
  port              = "80"
  notes             = "HTTP (for ACME challenges)"
}

# Allow PostgreSQL access within VPC (for test-services -> test-infra)
resource "vultr_firewall_rule" "test_postgres_vpc" {
  count             = var.create_test_env ? 1 : 0
  firewall_group_id = vultr_firewall_group.test[0].id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "10.0.0.0"
  subnet_size       = 24
  port              = "5432"
  notes             = "PostgreSQL within test VPC"
}

# Test Instance 1: Infrastructure (PostgreSQL + CIRISLens)
resource "vultr_instance" "test_infra" {
  count             = var.create_test_env ? 1 : 0
  plan              = "vc2-1c-2gb"  # 1 vCPU, 2GB RAM ~$12/mo
  region            = var.vultr_region
  os_id             = data.vultr_os.ubuntu.id
  label             = "ciris-test-infra"
  hostname          = "ciris-test-infra"
  enable_ipv6       = true
  backups           = "disabled"
  ddos_protection   = false
  activation_email  = false
  ssh_key_ids       = [vultr_ssh_key.cirisbridge.id]
  firewall_group_id = vultr_firewall_group.test[0].id
  vpc2_ids          = [vultr_vpc2.test[0].id]

  tags = ["cirisbridge", "test", "infra"]
}

# Test Instance 2: Services (CIRISBilling + CIRISProxy)
resource "vultr_instance" "test_services" {
  count             = var.create_test_env ? 1 : 0
  plan              = "vc2-2c-4gb"  # 2 vCPU, 4GB RAM ~$24/mo
  region            = var.vultr_region
  os_id             = data.vultr_os.ubuntu.id
  label             = "ciris-test-services"
  hostname          = "ciris-test-services"
  enable_ipv6       = true
  backups           = "disabled"
  ddos_protection   = false
  activation_email  = false
  ssh_key_ids       = [vultr_ssh_key.cirisbridge.id]
  firewall_group_id = vultr_firewall_group.test[0].id
  vpc2_ids          = [vultr_vpc2.test[0].id]

  tags = ["cirisbridge", "test", "services"]
}

# Test Instance 3: Scout (CIRISManager + CIRIS Agent)
resource "vultr_instance" "test_scout" {
  count             = var.create_test_env ? 1 : 0
  plan              = var.test_vultr_plan  # vc2-1c-1gb ~$6/mo
  region            = var.vultr_region
  os_id             = data.vultr_os.ubuntu.id
  label             = "ciris-test-scout"
  hostname          = "ciris-test-scout"
  enable_ipv6       = true
  backups           = "disabled"
  ddos_protection   = false
  activation_email  = false
  ssh_key_ids       = [vultr_ssh_key.cirisbridge.id]
  firewall_group_id = vultr_firewall_group.test[0].id
  vpc2_ids          = [vultr_vpc2.test[0].id]

  tags = ["cirisbridge", "test", "scout"]
}
