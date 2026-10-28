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
            "health-check.sh",
            "daily-status.sh",
            "weekly-status.sh",
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
            assert content.startswith(("#!/bin/bash", "#!/usr/bin/env bash")), \
                f"Script {script_file.name} should have bash shebang"

    def test_scripts_use_strict_mode(self, scripts_dir):
        """Test that scripts fail on unset variables and pipeline errors.

        The status checks deliberately omit -e: they run every check and
        report each failure rather than stopping at the first one.
        """
        for script_file in scripts_dir.glob("*.sh"):
            content = script_file.read_text()
            assert "set -euo pipefail" in content or "set -uo pipefail" in content, \
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
