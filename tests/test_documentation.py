"""
Tests for documentation completeness.
"""

from pathlib import Path

import pytest


class TestReadmeDocumentation:
    """Tests for README.md completeness."""

    def test_readme_exists(self, project_root):
        """Test that README.md exists."""
        readme = project_root / "README.md"
        assert readme.exists(), "README.md should exist"

    def test_readme_has_sections(self, project_root):
        """Test that README has required sections."""
        readme = project_root / "README.md"
        content = readme.read_text()

        required_sections = [
            "Overview",
            "Quick Start",
            "Architecture",
            "Cost",
        ]

        for section in required_sections:
            assert section in content, f"README should have {section} section"

    def test_readme_has_commands(self, project_root):
        """Test that README documents key commands."""
        readme = project_root / "README.md"
        content = readme.read_text()

        commands = [
            "deploy.sh",
            "health-check.sh",
            "terraform",
            "ansible",
        ]

        for cmd in commands:
            assert cmd in content, f"README should document {cmd}"


class TestClaudeMdDocumentation:
    """Tests for CLAUDE.md guidance file."""

    def test_claude_md_exists(self, project_root):
        """Test that CLAUDE.md exists."""
        claude_md = project_root / "CLAUDE.md"
        assert claude_md.exists(), "CLAUDE.md should exist"

    def test_claude_md_has_context(self, project_root):
        """Test that CLAUDE.md provides project context."""
        claude_md = project_root / "CLAUDE.md"
        content = claude_md.read_text()

        # Should explain what the project is
        assert "CIRISBridge" in content
        assert "orchestration" in content.lower() or "infrastructure" in content.lower()

    def test_claude_md_has_commands(self, project_root):
        """Test that CLAUDE.md documents build commands."""
        claude_md = project_root / "CLAUDE.md"
        content = claude_md.read_text()

        # Should have code blocks with commands
        assert "```" in content, "CLAUDE.md should have code blocks"
        assert "deploy" in content.lower()

    def test_claude_md_has_key_files(self, project_root):
        """Test that CLAUDE.md lists key files."""
        claude_md = project_root / "CLAUDE.md"
        content = claude_md.read_text()

        key_files = [
            "main.tf",
            "site.yml",
            "deploy.sh",
        ]

        for filename in key_files:
            assert filename in content, f"CLAUDE.md should mention {filename}"


class TestFsdDocumentation:
    """Tests for FSD.md specification."""

    def test_fsd_exists(self, project_root):
        """Test that FSD.md exists."""
        fsd = project_root / "FSD.md"
        assert fsd.exists(), "FSD.md should exist"

    def test_fsd_is_locked(self, project_root):
        """Test that FSD.md mentions it's locked."""
        fsd = project_root / "FSD.md"
        content = fsd.read_text()

        # FSD should indicate it's a locked specification
        assert "lock" in content.lower() or "specification" in content.lower()


class TestLicenseDocumentation:
    """Tests for LICENSE file."""

    def test_license_exists(self, project_root):
        """Test that LICENSE file exists."""
        license_file = project_root / "LICENSE"
        assert license_file.exists(), "LICENSE should exist"

    def test_license_is_apache2(self, project_root):
        """Test that license is Apache 2.0."""
        license_file = project_root / "LICENSE"
        content = license_file.read_text()

        assert "Apache" in content, "License should be Apache 2.0"
        assert "2.0" in content, "License should be version 2.0"


class TestExampleFiles:
    """Tests for example configuration files."""

    def test_env_example_exists(self, project_root):
        """Test that .env.example exists."""
        env_example = project_root / ".env.example"
        assert env_example.exists(), ".env.example should exist"

    def test_env_example_has_required_vars(self, project_root):
        """Test that .env.example documents required variables."""
        env_example = project_root / ".env.example"
        content = env_example.read_text()

        required_vars = [
            "VULTR_API_KEY",
            "HETZNER_API_TOKEN",
            "SSH_PUBLIC_KEY",
            "POSTGRES_PASSWORD",
        ]

        for var in required_vars:
            assert var in content, f".env.example should document {var}"

    def test_tfvars_example_exists(self, project_root):
        """Test that terraform.tfvars.example exists."""
        tfvars_example = project_root / "terraform" / "terraform.tfvars.example"
        assert tfvars_example.exists(), "terraform.tfvars.example should exist"

    def test_inventory_example_exists(self, project_root):
        """Test that inventory example exists."""
        inventory_example = project_root / "ansible" / "inventory" / "production.yml.example"
        assert inventory_example.exists(), "production.yml.example should exist"
