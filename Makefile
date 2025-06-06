.PHONY: clean install test build publish setup

# Standard Python and Pipenv commands (if installed)
PYTHON := $(shell command -v python3 || command -v python)
PIPENV := $(shell command -v pipenv)

# Default target: show help
all: help

help:
	@echo "Please use \`make <target>\`, where <target> is one of:"
	@echo "  setup         to create the Pipenv environment and install dependencies"
	@echo "  install       to install the package locally (editable mode)"
	@echo "  test          to run unit tests"
	@echo "  build         to create distributions (sdist & wheel)"
	@echo "  publish       to upload the package to PyPI"
	@echo "  publish-test  to upload the package to Test PyPI"
	@echo "  clean         to remove temporary files and builds"

# ----------------------------------------
# clean: remove old builds, __pycache__, etc.
# ----------------------------------------
clean:
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf build/ dist/ *.egg-info

# ----------------------------------------
# setup: create a Pipenv environment and install dependencies
# (uses Pipfile / Pipfile.lock)
# ----------------------------------------
setup:
	@if [ -z "$(PIPENV)" ]; then \
		echo "Error: pipenv is not installed. Please install it first: pip install pipenv"; exit 1; \
	fi
	# Initialize Pipenv and install all dependencies (including dev)
	pipenv install --dev

# ----------------------------------------
# install: install the package locally (editable mode)
# ----------------------------------------
install: clean setup
	# Inside the Pipenv shell, install our package in editable mode
	pipenv run pip install -e .

# ----------------------------------------
# test: run unit tests
# ----------------------------------------
test: setup
	pipenv run $(PYTHON) -m unittest discover tests/

# ----------------------------------------
# build: create sdist and wheel via PEP 517
# ----------------------------------------
build: clean setup
	# Requires a [build-system] section in pyproject.toml
	pipenv run $(PYTHON) -m build

# ----------------------------------------
# publish: upload package to Test PyPI (via twine)
# ----------------------------------------
publish-test: build
	# Upload to Test PyPI; ensure ~/.pypirc has a [testpypi] section
	pipenv run twine upload --repository testpypi dist/*

# ----------------------------------------
# publish: upload package to PyPI (via twine)
# ----------------------------------------
publish: build
	# Ensure Twine credentials are configured (e.g. in ~/.pypirc)
	pipenv run twine upload dist/*
