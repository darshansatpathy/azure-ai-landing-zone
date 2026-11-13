.PHONY: install check test policy fmt docs audit

install:
	python -m venv .venv && .venv/bin/pip install -e ".[dev]"

check:
	ruff check . && ruff format --check . && mypy && pytest --cov=tfpolicy --cov-fail-under=85

test:
	pytest

policy:
	tfpolicy check && tfpolicy fmt-check terraform

docs:
	tfpolicy rules --format markdown > docs/policies.md

audit:
	pip-audit --skip-editable
