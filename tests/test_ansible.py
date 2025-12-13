"""
Tests for Ansible configuration.
"""

import subprocess
from pathlib import Path

import pytest
import yaml


class TestAnsibleStructure:
    """Tests for Ansible directory structure."""

    def test_required_directories_exist(self, ansible_dir):
        """Test that required directories exist."""
        required_dirs = [
            "inventory",
            "playbooks",
            "roles",
            "roles/common",
            "roles/constellation",
            "roles/postgres",
            "roles/caddy",
            "roles/billing",
            "roles/proxy",
        ]

        for dirname in required_dirs:
            dirpath = ansible_dir / dirname
            assert dirpath.exists(), f"Missing required directory: {dirname}"

    def test_required_files_exist(self, ansible_dir):
        """Test that required files exist."""
        required_files = [
            "ansible.cfg",
            "inventory/production.yml.example",
            "playbooks/site.yml",
            "playbooks/dns.yml",
            "playbooks/billing.yml",
            "playbooks/proxy.yml",
        ]

        for filename in required_files:
            filepath = ansible_dir / filename
            assert filepath.exists(), f"Missing required file: {filename}"


class TestAnsibleSyntax:
    """Tests for Ansible syntax validation."""

    def test_playbook_syntax(self, ansible_dir):
        """Test that playbooks have valid YAML syntax."""
        playbooks_dir = ansible_dir / "playbooks"

        for playbook_file in playbooks_dir.glob("*.yml"):
            try:
                with open(playbook_file) as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {playbook_file.name}: {e}")

    def test_inventory_syntax(self, ansible_dir):
        """Test that inventory example has valid YAML syntax."""
        inventory_file = ansible_dir / "inventory" / "production.yml.example"

        try:
            with open(inventory_file) as f:
                inventory = yaml.safe_load(f)

            # Check basic structure
            assert "all" in inventory, "Inventory should have 'all' group"
            assert "children" in inventory["all"], "Inventory should have children groups"

        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in inventory: {e}")

    def test_ansible_lint(self, ansible_dir):
        """Test that Ansible configuration passes linting."""
        # Check if ansible-lint is available
        try:
            result = subprocess.run(
                ["ansible-lint", "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip("ansible-lint not installed")
        except FileNotFoundError:
            pytest.skip("ansible-lint not installed")

        # Run ansible-lint on playbooks
        result = subprocess.run(
            ["ansible-lint", "playbooks/"],
            cwd=ansible_dir,
            capture_output=True,
            text=True,
        )

        # Warning: ansible-lint can be strict, allow some warnings
        if result.returncode != 0 and "error" in result.stdout.lower():
            pytest.fail(f"Ansible lint errors:\n{result.stdout}")


class TestAnsibleRoles:
    """Tests for Ansible role structure."""

    @pytest.mark.parametrize("role", [
        "common",
        "constellation",
        "postgres",
        "caddy",
        "billing",
        "proxy",
    ])
    def test_role_has_tasks(self, ansible_dir, role):
        """Test that each role has a tasks/main.yml."""
        tasks_file = ansible_dir / "roles" / role / "tasks" / "main.yml"
        assert tasks_file.exists(), f"Role {role} missing tasks/main.yml"

        # Verify it's valid YAML
        try:
            with open(tasks_file) as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in {role}/tasks/main.yml: {e}")

    @pytest.mark.parametrize("role", [
        "common",
        "constellation",
        "postgres",
        "caddy",
        "billing",
        "proxy",
    ])
    def test_role_has_handlers(self, ansible_dir, role):
        """Test that roles with services have handlers."""
        handlers_file = ansible_dir / "roles" / role / "handlers" / "main.yml"

        if role != "common":  # common might not need handlers
            assert handlers_file.exists(), f"Role {role} missing handlers/main.yml"


class TestAnsibleTemplates:
    """Tests for Ansible Jinja2 templates."""

    def test_templates_have_jinja2_extension(self, ansible_dir):
        """Test that templates use .j2 extension."""
        for template_dir in ansible_dir.glob("roles/*/templates"):
            for template_file in template_dir.glob("*"):
                if template_file.is_file():
                    assert template_file.suffix == ".j2", \
                        f"Template {template_file} should have .j2 extension"

    def test_constellation_templates(self, ansible_dir):
        """Test that Constellation role has required templates."""
        templates_dir = ansible_dir / "roles" / "constellation" / "templates"

        required_templates = [
            "docker-compose.yml.j2",
            "config.cfg.j2",
            "zones.yaml.j2",
        ]

        for template in required_templates:
            template_path = templates_dir / template
            assert template_path.exists(), f"Missing template: {template}"

    def test_postgres_templates(self, ansible_dir):
        """Test that PostgreSQL role has required templates."""
        templates_dir = ansible_dir / "roles" / "postgres" / "templates"

        required_templates = [
            "docker-compose.yml.j2",
            "postgresql.conf.j2",
            "pg_hba.conf.j2",
        ]

        for template in required_templates:
            template_path = templates_dir / template
            assert template_path.exists(), f"Missing template: {template}"

    def test_templates_reference_variables(self, ansible_dir):
        """Test that templates reference expected variables."""
        # Check Caddyfile template
        caddyfile = ansible_dir / "roles" / "caddy" / "templates" / "Caddyfile.j2"
        content = caddyfile.read_text()

        assert "{{ dns_soa }}" in content, "Caddyfile should reference dns_soa"
        assert "{{ billing_port }}" in content, "Caddyfile should reference billing_port"


class TestAnsiblePlaybooks:
    """Tests for Ansible playbook content."""

    def test_site_playbook_includes_all_roles(self, ansible_dir):
        """Test that site.yml includes all service roles."""
        site_yml = ansible_dir / "playbooks" / "site.yml"
        content = site_yml.read_text()

        required_roles = [
            "common",
            "constellation",
            "postgres",
            "caddy",
            "billing",
            "proxy",
        ]

        for role in required_roles:
            assert role in content, f"site.yml should include role: {role}"

    def test_playbooks_have_tags(self, ansible_dir):
        """Test that playbooks use tags for selective execution."""
        site_yml = ansible_dir / "playbooks" / "site.yml"
        content = site_yml.read_text()

        assert "tags:" in content, "Playbooks should use tags"

    def test_playbooks_use_become(self, ansible_dir):
        """Test that playbooks use become for privilege escalation."""
        for playbook_file in (ansible_dir / "playbooks").glob("*.yml"):
            content = playbook_file.read_text()
            assert "become: true" in content or "become: yes" in content, \
                f"{playbook_file.name} should use become for privilege escalation"
