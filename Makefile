.DEFAULT_GOAL := help

.PHONY: help install format lint typecheck test check pre-commit

help: ## Show available development commands
	@awk 'BEGIN {FS = ":.*## "; printf "Conductor development commands:\n"} /^[a-zA-Z_-]+:.*?## / {printf "  %-14s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install the project and development dependencies
	python -m pip install -e '.[dev]'

format: ## Format Python sources
	python -m black backend/src tests
	python -m ruff check --fix backend/src tests

lint: ## Check Python formatting and lint rules
	python -m black --check backend/src tests
	python -m ruff check backend/src tests

typecheck: ## Run static type analysis
	python -m mypy backend/src tests

test: ## Run the test suite
	python -m pytest --cov=conductor --cov-report=term-missing

check: lint typecheck test ## Run all required local checks

pre-commit: ## Run every pre-commit hook
	python -m pre_commit run --all-files
