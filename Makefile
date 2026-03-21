VENV ?= .venv
PYTHON ?= python3
VENV_PYTHON := $(VENV)/bin/python
PIP := $(VENV_PYTHON) -m pip

.PHONY: setup fmt lint test test-rust test-python typecheck doc examples bench audit license ci clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	cargo fetch

fmt:
	cargo fmt --all
	$(VENV_PYTHON) -m ruff format python tests/python

lint:
	cargo clippy --workspace --all-targets --all-features -- -D warnings
	$(VENV_PYTHON) -m ruff check python tests/python

typecheck:
	$(VENV_PYTHON) -m mypy python

test-rust:
	cargo test --workspace --all-features --all-targets
	cargo test -p rust-contract-checks --doc

test-python:
	$(VENV_PYTHON) -m pytest tests/python

test: test-rust test-python

doc:
	cargo doc --workspace --all-features --no-deps

examples:
	$(VENV_PYTHON) examples/quickstart.py
	cargo run -p rust-contract-checks --example quickstart

bench:
	cargo bench -p rust-contract-checks --all-features

audit:
	cargo audit
	$(VENV_PYTHON) -m pip_audit

license:
	cargo deny check licenses bans sources

ci: fmt lint typecheck test doc examples

clean:
	rm -rf $(VENV)
