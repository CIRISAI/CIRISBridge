# CIRISBridge Terraform Variables

# =============================================================================
# Provider Credentials
# =============================================================================

variable "vultr_api_key" {
  description = "Vultr API key"
  type        = string
  sensitive   = true
}

variable "hetzner_api_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

# =============================================================================
# SSH Configuration
# =============================================================================

variable "ssh_public_key" {
  description = "SSH public key for server access"
  type        = string
}

variable "admin_ip" {
  description = "Admin IP address for SSH access (your IP)"
  type        = string
}

# =============================================================================
# Vultr Configuration
# =============================================================================

variable "vultr_region" {
  description = "Vultr region for primary instance"
  type        = string
  default     = "ord"  # Chicago - close to existing infra

  # Available US regions:
  # - ewr: New Jersey
  # - ord: Chicago
  # - dfw: Dallas
  # - lax: Los Angeles
  # - sea: Seattle
  # - atl: Atlanta
  # - mia: Miami
}

variable "vultr_plan" {
  description = "Vultr plan ID"
  type        = string
  default     = "vc2-2c-4gb"  # 2 vCPU, 4GB RAM, 80GB SSD - ~$24/mo

  # Options:
  # - vc2-1c-1gb: 1 vCPU, 1GB RAM - ~$6/mo (minimal)
  # - vc2-1c-2gb: 1 vCPU, 2GB RAM - ~$12/mo
  # - vc2-2c-4gb: 2 vCPU, 4GB RAM - ~$24/mo (recommended)
  # - vc2-4c-8gb: 4 vCPU, 8GB RAM - ~$48/mo
}

# =============================================================================
# Hetzner Configuration
# =============================================================================

variable "hetzner_location" {
  description = "Hetzner datacenter location"
  type        = string
  default     = "fsn1"  # Falkenstein, Germany

  # Options:
  # - fsn1: Falkenstein, Germany
  # - nbg1: Nuremberg, Germany
  # - hel1: Helsinki, Finland
  # - ash: Ashburn, USA (not for geo-redundancy)
}

variable "hetzner_server_type" {
  description = "Hetzner server type"
  type        = string
  default     = "cx22"  # 2 vCPU, 4GB RAM, 40GB SSD - ~€4/mo

  # Options:
  # - cx11: 1 vCPU, 2GB RAM - ~€4/mo
  # - cx22: 2 vCPU, 4GB RAM - ~€6/mo (recommended)
  # - cx32: 4 vCPU, 8GB RAM - ~€12/mo
}

variable "hetzner_volume_size" {
  description = "Hetzner block storage size in GB for PostgreSQL replica"
  type        = number
  default     = 20  # ~€1/mo
}

# =============================================================================
# Domain Configuration
# =============================================================================

variable "primary_domain" {
  description = "Primary domain (Vultr SOA)"
  type        = string
  default     = "ciris-services-1.ai"
}

variable "secondary_domain" {
  description = "Secondary domain (Hetzner SOA)"
  type        = string
  default     = "ciris-services-2.ai"
}
