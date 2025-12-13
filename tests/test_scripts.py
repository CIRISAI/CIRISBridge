"""
Tests for shell scripts.
"""

import os
import subprocess
from pathlib import Path

import pytest


class TestScriptStructure:
    """Tests for script file structure."""

    def test_required_scripts_exist(self, scripts_dir):
        """Test that required scripts exist."""
        required_scripts = [
            "deploy.sh",
            "health-check.sh",
            "sync-records.sh",
            "backup-db.sh",
            "failover-db.sh",
        ]

        for script in required_scripts:
            script_path = scripts_dir / script
            assert script_path.exists(), f"Missing required script: {script}"

    def test_scripts_are_executable(self, scripts_dir):
        """Test that scripts are executable."""
        for script_file in scripts_dir.glob("*.sh"):
            assert os.access(script_file, os.X_OK), \
                f"Script {script_file.name} should be executable"

    def test_scripts_have_shebang(self, scripts_dir):
        """Test that scripts have proper shebang."""
        for script_file in scripts_dir.glob("*.sh"):
            content = script_file.read_text()
            assert content.startswith("#!/bin/bash"), \
                f"Script {script_file.name} should have bash shebang"

    def test_scripts_use_strict_mode(self, scripts_dir):
        """Test that scripts use strict mode (set -euo pipefail)."""
        for script_file in scripts_dir.glob("*.sh"):
            content = script_file.read_text()
            assert "set -euo pipefail" in content, \
                f"Script {script_file.name} should use strict mode"


class TestShellcheck:
    """Tests using shellcheck for script analysis."""

    def test_shellcheck_available(self):
        """Check if shellcheck is available."""
        try:
            result = subprocess.run(
                ["shellcheck", "--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.skip("shellcheck not installed")
        except FileNotFoundError:
            pytest.skip("shellcheck not installed")

    def test_scripts_pass_shellcheck(self, scripts_dir):
        """Test that scripts pass shellcheck."""
        # Check if shellcheck is available
        try:
            subprocess.run(["shellcheck", "--version"], capture_output=True)
        except FileNotFoundError:
            pytest.skip("shellcheck not installed")

        for script_file in scripts_dir.glob("*.sh"):
            result = subprocess.run(
                ["shellcheck", "-S", "warning", str(script_file)],
                capture_output=True,
                text=True,
            )

            # Allow some warnings but fail on errors
            if result.returncode != 0 and "error" in result.stdout.lower():
                pytest.fail(f"Shellcheck errors in {script_file.name}:\n{result.stdout}")


class TestDeployScript:
    """Tests for deploy.sh script."""

    def test_deploy_script_has_commands(self, scripts_dir):
        """Test that deploy.sh handles all deployment commands."""
        deploy_script = scripts_dir / "deploy.sh"
        content = deploy_script.read_text()

        commands = ["all", "infra", "services", "dns", "billing", "proxy"]

        for cmd in commands:
            assert cmd in content, f"deploy.sh should handle command: {cmd}"

    def test_deploy_script_checks_prereqs(self, scripts_dir):
        """Test that deploy.sh checks prerequisites."""
        deploy_script = scripts_dir / "deploy.sh"
        content = deploy_script.read_text()

        assert "terraform" in content, "deploy.sh should check for terraform"
        assert "ansible" in content, "deploy.sh should check for ansible"

    def test_deploy_script_prompts_for_confirmation(self, scripts_dir):
        """Test that deploy.sh prompts before terraform apply."""
        deploy_script = scripts_dir / "deploy.sh"
        content = deploy_script.read_text()

        assert "read -p" in content, "deploy.sh should prompt for confirmation"


class TestHealthCheckScript:
    """Tests for health-check.sh script."""

    def test_health_check_checks_services(self, scripts_dir):
        """Test that health-check.sh checks all services."""
        health_script = scripts_dir / "health-check.sh"
        content = health_script.read_text()

        services = ["Billing", "Proxy", "DNS"]

        for service in services:
            assert service in content, f"health-check.sh should check {service}"

    def test_health_check_uses_curl(self, scripts_dir):
        """Test that health-check.sh uses curl for HTTP checks."""
        health_script = scripts_dir / "health-check.sh"
        content = health_script.read_text()

        assert "curl" in content, "health-check.sh should use curl"

    def test_health_check_uses_dig(self, scripts_dir):
        """Test that health-check.sh uses dig for DNS checks."""
        health_script = scripts_dir / "health-check.sh"
        content = health_script.read_text()

        assert "dig" in content, "health-check.sh should use dig for DNS checks"


class TestBackupScript:
    """Tests for backup-db.sh script."""

    def test_backup_uses_pg_dump(self, scripts_dir):
        """Test that backup-db.sh uses pg_dump."""
        backup_script = scripts_dir / "backup-db.sh"
        content = backup_script.read_text()

        assert "pg_dump" in content, "backup-db.sh should use pg_dump"

    def test_backup_compresses_output(self, scripts_dir):
        """Test that backup-db.sh compresses backups."""
        backup_script = scripts_dir / "backup-db.sh"
        content = backup_script.read_text()

        assert "gzip" in content, "backup-db.sh should compress with gzip"

    def test_backup_cleans_old_files(self, scripts_dir):
        """Test that backup-db.sh cleans old backups."""
        backup_script = scripts_dir / "backup-db.sh"
        content = backup_script.read_text()

        assert "find" in content and "-delete" in content, \
            "backup-db.sh should clean old backups"


class TestFailoverScript:
    """Tests for failover-db.sh script."""

    def test_failover_checks_status(self, scripts_dir):
        """Test that failover-db.sh can check database status."""
        failover_script = scripts_dir / "failover-db.sh"
        content = failover_script.read_text()

        assert "status" in content, "failover-db.sh should support status command"
        assert "pg_isready" in content, "failover-db.sh should check pg_isready"

    def test_failover_prompts_confirmation(self, scripts_dir):
        """Test that failover-db.sh prompts before promoting."""
        failover_script = scripts_dir / "failover-db.sh"
        content = failover_script.read_text()

        assert "Are you sure" in content or "read -p" in content, \
            "failover-db.sh should prompt before promotion"

    def test_failover_uses_pg_ctl_promote(self, scripts_dir):
        """Test that failover-db.sh uses pg_ctl promote."""
        failover_script = scripts_dir / "failover-db.sh"
        content = failover_script.read_text()

        assert "pg_ctl promote" in content, "failover-db.sh should use pg_ctl promote"


class TestSyncRecordsScript:
    """Tests for sync-records.sh script."""

    def test_sync_records_syncs_to_both_regions(self, scripts_dir):
        """Test that sync-records.sh syncs to both regions."""
        sync_script = scripts_dir / "sync-records.sh"
        content = sync_script.read_text()

        assert "VULTR_IP" in content, "sync-records.sh should reference Vultr IP"
        assert "HETZNER_IP" in content, "sync-records.sh should reference Hetzner IP"

    def test_sync_records_uses_rest_api(self, scripts_dir):
        """Test that sync-records.sh uses Constellation REST API."""
        sync_script = scripts_dir / "sync-records.sh"
        content = sync_script.read_text()

        assert "curl" in content, "sync-records.sh should use curl"
        assert "8080" in content, "sync-records.sh should target API port 8080"
