"""
Pytest fixtures for CIRISBridge tests.
"""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def terraform_dir(project_root):
    """Return the terraform directory."""
    return project_root / "terraform"


@pytest.fixture
def ansible_dir(project_root):
    """Return the ansible directory."""
    return project_root / "ansible"


@pytest.fixture
def scripts_dir(project_root):
    """Return the scripts directory."""
    return project_root / "scripts"


@pytest.fixture
def sample_terraform_vars():
    """Sample Terraform variables for testing."""
    return {
        "vultr_api_key": "test-vultr-key-123",
        "hetzner_api_token": "test-hetzner-token-456",
        "ssh_public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItest test@test.com",
        "admin_ip": "192.168.1.1",
        "vultr_region": "ord",
        "vultr_plan": "vc2-2c-4gb",
        "hetzner_location": "fsn1",
        "hetzner_server_type": "cx22",
        "hetzner_volume_size": 20,
        "primary_domain": "test-services-1.ai",
        "secondary_domain": "test-services-2.ai",
    }


@pytest.fixture
def sample_ansible_vars():
    """Sample Ansible variables for testing."""
    return {
        "vultr_ip": "1.2.3.4",
        "hetzner_ip": "5.6.7.8",
        "primary_domain": "test-services-1.ai",
        "secondary_domain": "test-services-2.ai",
        "admin_email": "test@test.com",
        "postgres_password": "test-password",
        "replication_password": "test-replication",
        "billing_port": 8080,
        "proxy_port": 4000,
    }


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing shell commands."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )
        yield mock_run


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="cirisbridge_test_")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mock_ssh():
    """Mock SSH connections for testing."""
    with patch("subprocess.run") as mock_run:
        def ssh_side_effect(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""

            # Simulate different SSH commands
            if "pg_isready" in str(args):
                result.stdout = "accepting connections"
            elif "docker exec" in str(args):
                result.stdout = "OK"

            return result

        mock_run.side_effect = ssh_side_effect
        yield mock_run


@pytest.fixture
def mock_http_responses():
    """Mock HTTP responses for health checks."""
    responses = {
        "/health": {"status": "healthy", "database": "connected"},
        "/v1/billing/credits/check": {"has_credit": True, "credits_remaining": 10},
    }
    return responses
