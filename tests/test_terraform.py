"""
Tests for Terraform configuration.
"""

import subprocess
from pathlib import Path

import pytest


class TestTerraformSyntax:
    """Tests for Terraform syntax and formatting."""

    def test_terraform_files_exist(self, terraform_dir):
        """Test that required Terraform files exist."""
        required_files = [
            "main.tf",
            "variables.tf",
            "outputs.tf",
            "terraform.tfvars.example",
        ]

        for filename in required_files:
            filepath = terraform_dir / filename
            assert filepath.exists(), f"Missing required file: {filename}"

    def test_terraform_format(self, terraform_dir):
        """Test that Terraform files are properly formatted."""
        # Check if terraform is available
        try:
            result = subprocess.run(
                ["terraform", "version"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip("Terraform not installed")
        except FileNotFoundError:
            pytest.skip("Terraform not installed")

        # Run terraform fmt -check
        result = subprocess.run(
            ["terraform", "fmt", "-check", "-diff", "-recursive"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Terraform format check failed:\n{result.stdout}"

    def test_terraform_validate(self, terraform_dir, temp_dir, sample_terraform_vars):
        """Test that Terraform configuration is valid."""
        # Check if terraform is available
        try:
            result = subprocess.run(
                ["terraform", "version"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip("Terraform not installed")
        except FileNotFoundError:
            pytest.skip("Terraform not installed")

        # Create a temporary tfvars file
        tfvars_content = "\n".join(
            f'{k} = "{v}"' if isinstance(v, str) else f'{k} = {v}'
            for k, v in sample_terraform_vars.items()
        )

        tfvars_file = temp_dir / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        # Initialize terraform
        result = subprocess.run(
            ["terraform", "init", "-backend=false"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip(f"Terraform init failed: {result.stderr}")

        # Validate
        result = subprocess.run(
            ["terraform", "validate"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Terraform validate failed:\n{result.stderr}"


class TestTerraformVariables:
    """Tests for Terraform variables configuration."""

    def test_required_variables_defined(self, terraform_dir):
        """Test that all required variables are defined."""
        variables_tf = terraform_dir / "variables.tf"
        content = variables_tf.read_text()

        required_variables = [
            "vultr_api_key",
            "hetzner_api_token",
            "ssh_public_key",
            "admin_ip",
            "vultr_region",
            "vultr_plan",
            "hetzner_location",
            "hetzner_server_type",
        ]

        for var in required_variables:
            assert f'variable "{var}"' in content, f"Missing required variable: {var}"

    def test_sensitive_variables_marked(self, terraform_dir):
        """Test that sensitive variables are marked as sensitive."""
        variables_tf = terraform_dir / "variables.tf"
        content = variables_tf.read_text()

        # Check that API keys are marked sensitive
        assert "sensitive   = true" in content, "API keys should be marked sensitive"

    def test_default_values_reasonable(self, terraform_dir):
        """Test that default values are reasonable."""
        variables_tf = terraform_dir / "variables.tf"
        content = variables_tf.read_text()

        # Check defaults are set for non-sensitive values
        assert 'default     = "ord"' in content or 'default = "ord"' in content, "Default region should be set"


class TestTerraformOutputs:
    """Tests for Terraform outputs configuration."""

    def test_required_outputs_defined(self, terraform_dir):
        """Test that required outputs are defined."""
        outputs_tf = terraform_dir / "outputs.tf"
        content = outputs_tf.read_text()

        required_outputs = [
            "vultr_ip",
            "hetzner_ip",
            "ssh_us",        # Active/Active: US node
            "ssh_eu",        # Active/Active: EU node
            "ansible_inventory",
        ]

        for output in required_outputs:
            assert f'output "{output}"' in content, f"Missing required output: {output}"

    def test_ansible_inventory_output(self, terraform_dir):
        """Test that Ansible inventory output is properly formatted."""
        outputs_tf = terraform_dir / "outputs.tf"
        content = outputs_tf.read_text()

        # Should contain YAML structure markers
        assert "ansible_host:" in content, "Ansible inventory should contain ansible_host"
        assert "ansible_user:" in content, "Ansible inventory should contain ansible_user"


class TestTerraformResources:
    """Tests for Terraform resource definitions."""

    def test_firewall_rules_defined(self, terraform_dir):
        """Test that firewall rules are defined for both providers."""
        main_tf = terraform_dir / "main.tf"
        content = main_tf.read_text()

        # Check Vultr firewall
        assert "vultr_firewall_group" in content, "Vultr firewall group should be defined"
        assert "vultr_firewall_rule" in content, "Vultr firewall rules should be defined"

        # Check Hetzner firewall
        assert "hcloud_firewall" in content, "Hetzner firewall should be defined"

    def test_ssh_keys_defined(self, terraform_dir):
        """Test that SSH keys are defined for both providers."""
        main_tf = terraform_dir / "main.tf"
        content = main_tf.read_text()

        assert "vultr_ssh_key" in content, "Vultr SSH key should be defined"
        assert "hcloud_ssh_key" in content, "Hetzner SSH key should be defined"

    def test_instances_defined(self, terraform_dir):
        """Test that compute instances are defined."""
        main_tf = terraform_dir / "main.tf"
        content = main_tf.read_text()

        assert "vultr_instance" in content, "Vultr instance should be defined"
        assert "hcloud_server" in content, "Hetzner server should be defined"

    def test_required_ports_open(self, terraform_dir):
        """Test that required ports are opened in firewall rules."""
        main_tf = terraform_dir / "main.tf"
        content = main_tf.read_text()

        required_ports = ["22", "53", "80", "443"]

        for port in required_ports:
            assert f'"{port}"' in content or f"= {port}" in content, \
                f"Port {port} should be open in firewall"
