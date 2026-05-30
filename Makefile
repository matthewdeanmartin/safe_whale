UV ?= uv
BASH ?= bash
MAKEFLAGS += --no-print-directory
export PYTHONUTF8 := 1

PACKAGE := safe_whale
PYTHON_TARGETS := safe_whale tests

.PHONY: \
	sync \
	format format-python \
	format-check format-check-python \
	lint lint-check ruff-fix ruff-check pylint \
	security bandit \
	smoke test test-ci tox \
	typecheck typecheck-mypy \
	build \
	check check-ci \
	help

help:
	@echo "Targets:"
	@echo "  sync          Install / refresh dependencies"
	@echo "  format        Auto-format all code"
	@echo "  format-check  Check formatting without changes"
	@echo "  lint          Ruff fix"
	@echo "  lint-check    Ruff check (read-only)"
	@echo "  pylint        Advisory pylint run"
	@echo "  test          Run pytest suite with coverage"
	@echo "  test-ci       Run pytest (for CI)"
	@echo "  tox           Run tests through tox"
	@echo "  typecheck     Run mypy strict"
	@echo "  security      Run bandit"
	@echo "  build         Build wheel"
	@echo "  check         Full local quality gate"
	@echo "  check-ci      CI quality gate"

sync:
	@$(UV) sync

format: format-python

format-python:
	@$(UV) run isort $(PYTHON_TARGETS)
	@$(UV) run black $(PYTHON_TARGETS)
	@$(UV) run ruff check --fix --quiet $(PYTHON_TARGETS)
	@$(UV) run black $(PYTHON_TARGETS)

format-check: format-check-python

format-check-python:
	@$(UV) run isort --check-only $(PYTHON_TARGETS)
	@$(UV) run black --check $(PYTHON_TARGETS)
	@$(UV) run ruff check --quiet $(PYTHON_TARGETS)

lint: ruff-fix

lint-check: ruff-check

ruff-fix:
	@$(UV) run ruff check --fix --quiet $(PYTHON_TARGETS)

ruff-check:
	@$(UV) run ruff check --quiet $(PYTHON_TARGETS)

pylint:
	@$(UV) run pylint --persistent=n --score=n --reports=n $(PACKAGE) || true

security: bandit

bandit:
	@$(UV) run bandit -q -c pyproject.toml -r $(PACKAGE)

smoke:
	@$(UV) run safe-whale --help
	@$(UV) run safe-whale --version
	@"$(BASH)" scripts/basic_checks.sh

test:
	@$(UV) run pytest -q \
		--cov=$(PACKAGE) \
		--cov-report=html \
		--timeout=60

test-ci:
	@$(UV) run pytest -q \
		--cov=$(PACKAGE) \
		--cov-report=xml \
		--junitxml=junit.xml \
		--timeout=60

tox:
	@$(UV) run tox

typecheck: typecheck-mypy

typecheck-mypy:
	@$(UV) run mypy --hide-error-context $(PACKAGE) tests

build:
	@$(UV) build

check: lint-check security test typecheck
	@echo "All checks passed."

check-ci: lint-check security test-ci typecheck smoke
	@echo "CI checks passed."
