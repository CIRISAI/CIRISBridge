# CIRISBridge Makefile
# Common development and deployment tasks

.PHONY: help test test-cov lint lint-terraform lint-ansible lint-shell format deploy deploy-caddy deploy-billing deploy-proxy deploy-server deploy-status health clean

help:
	@echo "CIRISBridge Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make test      - Run all tests"
	@echo "  make lint      - Run linters"
	@echo "  make format    - Format Terraform files"
	@echo "  make deploy    - Deploy all services (site.yml)"
	@echo "  make deploy-<service> - Deploy one service (caddy, billing, proxy, server, status)"
	@echo "  make health    - Daily status check"
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

# Deployment (from ansible/, needs the vault password for production.yml)
PLAYBOOK = cd ansible && ansible-playbook -i inventory/production.yml playbooks/site.yml

deploy:
	$(PLAYBOOK)

deploy-caddy:
	$(PLAYBOOK) --tags caddy

deploy-billing:
	$(PLAYBOOK) --tags billing

deploy-proxy:
	$(PLAYBOOK) --tags proxy

deploy-server:
	$(PLAYBOOK) --tags ciris-server

deploy-status:
	$(PLAYBOOK) --tags ciris-status

# Health checks
health:
	./scripts/daily-status.sh

# Cleaning
clean:
	rm -rf terraform/.terraform
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
