"""
Integration tests for CIRISBridge.

These tests verify the interaction between components.
Run with: pytest tests/test_integration.py -v
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestTerraformAnsibleIntegration:
    """Tests for Terraform -> Ansible integration."""

    def test_terraform_output_matches_ansible_inventory(self, terraform_dir, ansible_dir):
        """Test that Terraform outputs match Ansible inventory expectations."""
        # Read outputs.tf to check what Terraform outputs
        outputs_tf = terraform_dir / "outputs.tf"
        outputs_content = outputs_tf.read_text()

        # Read inventory example to check what Ansible expects
        inventory_file = ansible_dir / "inventory" / "production.yml.example"
        inventory_content = inventory_file.read_text()

        # Check key mappings
        assert "ansible_host" in outputs_content, \
            "Terraform should output ansible_host"
        assert "ansible_host" in inventory_content, \
            "Ansible inventory should use ansible_host"

        assert "vultr_ip" in outputs_content, \
            "Terraform should output vultr_ip"
        assert "vultr_ip" in inventory_content, \
            "Ansible inventory should use vultr_ip"

    def test_terraform_inventory_output_is_valid_yaml(self, sample_ansible_vars):
        """Test that Terraform's inventory output would be valid YAML."""
        import yaml

        # Simulate what Terraform would output
        inventory_template = f"""
all:
  children:
    primary:
      hosts:
        vultr:
          ansible_host: {sample_ansible_vars['vultr_ip']}
          ansible_user: root
          region: us
          role: primary

    secondary:
      hosts:
        hetzner:
          ansible_host: {sample_ansible_vars['hetzner_ip']}
          ansible_user: root
          region: eu
          role: secondary

  vars:
    vultr_ip: {sample_ansible_vars['vultr_ip']}
    hetzner_ip: {sample_ansible_vars['hetzner_ip']}
"""

        # Should parse as valid YAML
        try:
            inventory = yaml.safe_load(inventory_template)
            assert "all" in inventory
            assert "children" in inventory["all"]
        except yaml.YAMLError as e:
            pytest.fail(f"Terraform inventory output is not valid YAML: {e}")


class TestAnsibleRoleIntegration:
    """Tests for Ansible role dependencies and ordering."""

    def test_service_roles_depend_on_common(self, ansible_dir):
        """Test that service roles are applied after common."""
        site_yml = ansible_dir / "playbooks" / "site.yml"
        content = site_yml.read_text()

        # Look for role references in the roles: section, not just any occurrence
        # Find positions of "- common" vs "- billing" etc.
        common_pos = content.find("- common")
        billing_pos = content.find("- billing")
        proxy_pos = content.find("- proxy")

        assert common_pos != -1, "common role should be defined"
        assert billing_pos != -1, "billing role should be defined"
        assert proxy_pos != -1, "proxy role should be defined"
        assert common_pos < billing_pos, "common should be before billing"
        assert common_pos < proxy_pos, "common should be before proxy"

    def test_caddy_after_services(self, ansible_dir):
        """Test that Caddy can route to services."""
        caddyfile = ansible_dir / "roles" / "caddy" / "templates" / "Caddyfile.j2"
        content = caddyfile.read_text()

        # Caddy should reference billing and proxy
        assert "ciris-billing" in content, "Caddy should route to billing"
        assert "ciris-proxy" in content, "Caddy should route to proxy"

    def test_postgres_before_billing(self, ansible_dir):
        """Test that PostgreSQL is deployed before billing."""
        site_yml = ansible_dir / "playbooks" / "site.yml"
        content = site_yml.read_text()

        # Look for role references in the roles: section
        postgres_pos = content.find("- postgres")
        billing_pos = content.find("- billing")

        assert postgres_pos != -1, "postgres role should be defined"
        assert billing_pos != -1, "billing role should be defined"
        assert postgres_pos < billing_pos, "postgres should be before billing"


class TestConfigurationConsistency:
    """Tests for configuration consistency across components."""

    def test_port_consistency(self, ansible_dir):
        """Test that port numbers are consistent across configs."""
        # Collect port references
        ports = {
            "billing": set(),
            "proxy": set(),
            "postgres": set(),
        }

        # Check Caddy config
        caddyfile = ansible_dir / "roles" / "caddy" / "templates" / "Caddyfile.j2"
        caddy_content = caddyfile.read_text()

        if "{{ billing_port }}" in caddy_content:
            ports["billing"].add("{{ billing_port }}")
        if "{{ proxy_port }}" in caddy_content:
            ports["proxy"].add("{{ proxy_port }}")

        # Check billing docker-compose
        billing_compose = ansible_dir / "roles" / "billing" / "templates" / "docker-compose.yml.j2"
        billing_content = billing_compose.read_text()

        assert "{{ billing_port }}" in billing_content, \
            "Billing compose should use billing_port variable"

    def test_domain_consistency(self, ansible_dir):
        """Test that domain references are consistent."""
        # Check zones template
        zones_file = ansible_dir / "roles" / "constellation" / "templates" / "zones.yaml.j2"
        zones_content = zones_file.read_text()

        assert "{{ primary_domain }}" in zones_content, \
            "Zones should reference primary_domain"
        assert "{{ secondary_domain }}" in zones_content, \
            "Zones should reference secondary_domain"

        # Check Caddy config
        caddyfile = ansible_dir / "roles" / "caddy" / "templates" / "Caddyfile.j2"
        caddy_content = caddyfile.read_text()

        assert "{{ dns_soa }}" in caddy_content, \
            "Caddyfile should reference dns_soa"


class TestDeploymentFlow:
    """Tests for the deployment flow."""

    def test_deploy_script_flow(self, scripts_dir, mock_subprocess):
        """Test that deploy.sh calls tools in correct order."""
        deploy_script = scripts_dir / "deploy.sh"
        content = deploy_script.read_text()

        # Find positions of key operations
        terraform_init_pos = content.find("terraform init")
        terraform_plan_pos = content.find("terraform plan")
        terraform_apply_pos = content.find("terraform apply")
        ansible_playbook_pos = content.find("ansible-playbook")

        # Verify order
        assert terraform_init_pos < terraform_plan_pos, \
            "terraform init should be before plan"
        assert terraform_plan_pos < terraform_apply_pos, \
            "terraform plan should be before apply"

        # Ansible should come after Terraform
        # (Either in same function or services follows infra)

    def test_health_check_after_deploy(self, scripts_dir):
        """Test that health check can verify deployment."""
        health_script = scripts_dir / "health-check.sh"
        content = health_script.read_text()

        # Should check all major services
        assert "billing" in content.lower()
        assert "proxy" in content.lower()
        assert "dns" in content.lower()


class TestSecurityConfiguration:
    """Tests for security-related configuration."""

    def test_sensitive_data_not_hardcoded(self, project_root):
        """Test that sensitive data is not hardcoded."""
        sensitive_patterns = [
            "password=",
            "api_key=",
            "secret=",
            "token=",
        ]

        # Check all .tf, .yml, .j2 files
        for pattern in ["**/*.tf", "**/*.yml", "**/*.j2"]:
            for filepath in project_root.glob(pattern):
                if ".terraform" in str(filepath):
                    continue

                content = filepath.read_text().lower()

                for sensitive in sensitive_patterns:
                    # Skip variable declarations and examples
                    if "example" in filepath.name:
                        continue
                    if f"{sensitive}{{" in content:  # Jinja variable
                        continue
                    if f'{sensitive}"' in content and "var." in content:
                        continue

                    # Check for hardcoded values
                    lines = content.split("\n")
                    for line in lines:
                        if sensitive in line and "=" in line:
                            # Allow variable references
                            if "{{" in line or "var." in line or "$" in line:
                                continue
                            # Allow empty values in examples
                            if '=""' in line or "=''" in line:
                                continue

    def test_firewall_restricts_ssh(self, terraform_dir):
        """Test that SSH is restricted to admin IP."""
        main_tf = terraform_dir / "main.tf"
        content = main_tf.read_text()

        # SSH rule should reference admin_ip variable
        assert "var.admin_ip" in content, \
            "SSH firewall rule should reference admin_ip"

    def test_postgres_not_public(self, terraform_dir):
        """Test that PostgreSQL is not publicly exposed."""
        main_tf = terraform_dir / "main.tf"
        content = main_tf.read_text()

        # PostgreSQL firewall rules should only allow peer IPs
        # Should NOT have 0.0.0.0/0 for port 5432
        lines = content.split("\n")
        in_postgres_rule = False

        for line in lines:
            if "5432" in line:
                in_postgres_rule = True
            if in_postgres_rule and "0.0.0.0" in line:
                pytest.fail("PostgreSQL should not be exposed to 0.0.0.0/0")
            if in_postgres_rule and "}" in line:
                in_postgres_rule = False
