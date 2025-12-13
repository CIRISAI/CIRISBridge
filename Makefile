# CIRISBridge Makefile
# Common development and deployment tasks

.PHONY: help test lint format deploy health clean

help:
	@echo "CIRISBridge Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make test      - Run all tests"
	@echo "  make lint      - Run linters"
	@echo "  make format    - Format Terraform files"
	@echo "  make deploy    - Deploy all services"
	@echo "  make health    - Check service health"
	@echo "  make clean     - Clean temp files"
	@echo ""

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=. --cov-report=html

# Linting
lint: lint-terraform lint-ansible lint-shell

lint-terraform:
	@echo "Checking Terraform format..."
	cd terraform && terraform fmt -check -diff -recursive

lint-ansible:
	@echo "Checking Ansible syntax..."
	cd ansible && ansible-lint playbooks/ || true

lint-shell:
	@echo "Checking shell scripts..."
	shellcheck scripts/*.sh || true

# Formatting
format:
	cd terraform && terraform fmt -recursive

# Deployment
deploy:
	./scripts/deploy.sh all

deploy-infra:
	./scripts/deploy.sh infra

deploy-services:
	./scripts/deploy.sh services

deploy-dns:
	./scripts/deploy.sh dns

deploy-billing:
	./scripts/deploy.sh billing

deploy-proxy:
	./scripts/deploy.sh proxy

# Health checks
health:
	./scripts/health-check.sh

# Database operations
backup:
	./scripts/backup-db.sh

failover-status:
	./scripts/failover-db.sh status

# Cleaning
clean:
	rm -rf terraform/.terraform
	rm -rf terraform/terraform.tfstate*
	rm -rf ansible/.ansible_cache
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf __pycache__
	find . -name "*.pyc" -delete

# Setup
setup:
	pip install -r requirements-dev.txt
	cd terraform && terraform init -backend=false

# Validate
validate: lint
	cd terraform && terraform validate
	cd ansible && ansible-playbook --syntax-check playbooks/site.yml
