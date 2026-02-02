# Cerberus CTF Platform - Backend Makefile
# Development commands for testing, linting, and formatting

.PHONY: help install dev test lint format type-check clean docker-build docker-run migrate

# Default target
help:
	@echo "Cerberus CTF Platform - Backend Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  install      Install production dependencies"
	@echo "  dev          Install development dependencies"
	@echo "  test         Run all tests"
	@echo "  test-unit    Run unit tests only"
	@echo "  test-int     Run integration tests only"
	@echo "  test-cov     Run tests with coverage report"
	@echo "  lint         Run linter (ruff)"
	@echo "  format       Format code (black + isort)"
	@echo "  type-check   Run type checker (mypy)"
	@echo "  check        Run all checks (lint + type-check + test)"
	@echo "  clean        Clean build artifacts"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run Docker container"
	@echo "  migrate      Run database migrations"
	@echo "  migrate-new  Create new migration"
	@echo "  shell        Start Python shell with app context"

# Python settings
PYTHON := python3
PIP := pip3
PYTEST := pytest
MYPY := mypy
RUFF := ruff
BLACK := black
ISORT := isort

# Directories
SRC_DIR := app
TEST_DIR := tests
ALEMBIC_DIR := alembic

# Docker settings
DOCKER_IMAGE := cerberus-backend
DOCKER_TAG := latest

# =============================================================================
# Installation
# =============================================================================

install:
	$(PIP) install -r requirements.txt

dev: install
	$(PIP) install pytest pytest-asyncio pytest-cov pytest-mock
	$(PIP) install factory-boy faker testcontainers
	$(PIP) install mypy ruff black isort pre-commit
	$(PIP) install types-redis types-python-dateutil types-passlib
	pre-commit install

# =============================================================================
# Testing
# =============================================================================

test:
	$(PYTEST) $(TEST_DIR) -v --tb=short

test-unit:
	$(PYTEST) $(TEST_DIR)/unit -v --tb=short

test-int:
	$(PYTEST) $(TEST_DIR)/integration -v --tb=short

test-e2e:
	$(PYTEST) $(TEST_DIR)/e2e -v --tb=short

test-cov:
	$(PYTEST) $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing

test-cov-domain:
	$(PYTEST) $(TEST_DIR)/unit/domain -v --cov=$(SRC_DIR)/domain --cov-report=term-missing --cov-fail-under=100

# =============================================================================
# Code Quality
# =============================================================================

lint:
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)

lint-fix:
	$(RUFF) check $(SRC_DIR) $(TEST_DIR) --fix

format:
	$(BLACK) $(SRC_DIR) $(TEST_DIR)
	$(ISORT) $(SRC_DIR) $(TEST_DIR)

format-check:
	$(BLACK) --check $(SRC_DIR) $(TEST_DIR)
	$(ISORT) --check-only $(SRC_DIR) $(TEST_DIR)

type-check:
	$(MYPY) $(SRC_DIR) --strict --ignore-missing-imports

check: lint type-check test

# =============================================================================
# Database
# =============================================================================

migrate:
	alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

migrate-down:
	alembic downgrade -1

migrate-history:
	alembic history

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) -f docker/Dockerfile .

docker-build-dev:
	docker build -t $(DOCKER_IMAGE):dev --target development -f docker/Dockerfile .

docker-run:
	docker run -p 8000:8000 --env-file .env $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-run-dev:
	docker run -p 8000:8000 -v $(PWD)/app:/app/app --env-file .env $(DOCKER_IMAGE):dev

docker-push:
	docker push $(DOCKER_IMAGE):$(DOCKER_TAG)

# =============================================================================
# Development
# =============================================================================

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

shell:
	$(PYTHON) -i -c "from app.main import app; print('App loaded. Use app to access.')"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# =============================================================================
# CI/CD Helpers
# =============================================================================

ci-lint:
	$(RUFF) check $(SRC_DIR) $(TEST_DIR) --output-format=github

ci-test:
	$(PYTEST) $(TEST_DIR) -v --tb=short --junitxml=test-results.xml

ci-cov:
	$(PYTEST) $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=xml --cov-report=term
