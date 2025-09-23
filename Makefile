.PHONY: clean install test build publish setup

# Standard Python and Pipenv commands (if installed)
PYTHON := $(shell command -v python3 || command -v python)
PIPENV := $(shell command -v pipenv)

# Default target: show help
all: help

help:
	@echo "Please use \`make <target>\`, where <target> is one of:"
	@echo "  setup         to create the Pipenv environment and install dependencies"
	@echo "  sync-deps     to synchronize all dependency files"
	@echo "  check-deps    to check if dependency files are in sync"
	@echo "  update-deps   to update all dependencies to latest versions"
	@echo "  install       to install the package locally (editable mode)"
	@echo "  test          to run unit tests"
	@echo "  build         to create distributions (sdist & wheel)"
	@echo "  publish       to upload the package to PyPI"
	@echo "  publish-test  to upload the package to Test PyPI"
	@echo "  release       to create a GitHub release after PyPI upload"
	@echo "  clean         to remove temporary files and builds"
	@echo "  check-readers to verify all reader classes are in __all__"

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

# ----------------------------------------
# release: create GitHub release with built artifacts
# ----------------------------------------
release: build
	@echo "Creating GitHub release..."
	@# Extract version from pyproject.toml
	@VERSION=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Creating release for version: $$VERSION"; \
	git tag -a "v$$VERSION" -m "Release version $$VERSION" 2>/dev/null || echo "Tag v$$VERSION already exists"; \
	git push origin "v$$VERSION" 2>/dev/null || echo "Tag already pushed"; \
	if command -v gh > /dev/null; then \
		gh release create "v$$VERSION" \
			--title "SeaSenseLib v$$VERSION" \
			--notes "Release version $$VERSION" \
			--draft \
			dist/seasenselib-$$VERSION.tar.gz \
			dist/seasenselib-$$VERSION-py3-none-any.whl; \
		echo "GitHub release created as draft. Please edit and publish manually."; \
	else \
		echo "GitHub CLI (gh) not found. Please create release manually at:"; \
		echo "https://github.com/ocean-uhh/seasenselib/releases/new"; \
		echo "Tag: v$$VERSION"; \
		echo "Upload files: dist/seasenselib-$$VERSION.tar.gz and dist/seasenselib-$$VERSION-py3-none-any.whl"; \
	fi

# ----------------------------------------
# check-readers: verify all reader classes are in __all__
# ----------------------------------------
check-readers:
	@echo "Checking readers completeness..."
	@$(PYTHON) scripts/check_readers_completeness.py

# ----------------------------------------
# sync-deps: synchronize all dependency files
# ----------------------------------------
sync-deps:
	@echo "Synchronizing dependency files..."
	@if [ -z "$(PIPENV)" ]; then \
		echo "Error: pipenv is not installed. Please install it first: pip install pipenv"; exit 1; \
	fi
	# Generate requirements.txt from Pipfile
	pipenv requirements > requirements.txt
	# Generate requirements-dev.txt from Pipfile (dev dependencies)
	pipenv requirements --dev > requirements-dev.txt
	@echo "Dependency files synchronized!"

# ----------------------------------------
# check-deps: check if dependency files are in sync
# ----------------------------------------
check-deps:
	@echo "Checking dependency synchronization..."
	@if [ -z "$(PIPENV)" ]; then \
		echo "Error: pipenv is not installed. Please install it first: pip install pipenv"; exit 1; \
	fi
	# Check if requirements.txt matches Pipfile
	@pipenv requirements > /tmp/current_requirements.txt
	@if ! diff -q requirements.txt /tmp/current_requirements.txt > /dev/null 2>&1; then \
		echo "❌ requirements.txt is out of sync with Pipfile"; \
		echo "Run 'make sync-deps' to synchronize"; \
		exit 1; \
	else \
		echo "✅ requirements.txt is in sync"; \
	fi
	# Check if requirements-dev.txt matches Pipfile
	@pipenv requirements --dev > /tmp/current_requirements_dev.txt
	@if ! diff -q requirements-dev.txt /tmp/current_requirements_dev.txt > /dev/null 2>&1; then \
		echo "❌ requirements-dev.txt is out of sync with Pipfile"; \
		echo "Run 'make sync-deps' to synchronize"; \
		exit 1; \
	else \
		echo "✅ requirements-dev.txt is in sync"; \
	fi
	@rm -f /tmp/current_requirements*.txt
	@echo "All dependency files are synchronized! 🎉"

# ----------------------------------------
# update-deps: update all dependencies to latest versions
# ----------------------------------------
update-deps:
	@echo "Updating dependencies..."
	@if [ -z "$(PIPENV)" ]; then \
		echo "Error: pipenv is not installed. Please install it first: pip install pipenv"; exit 1; \
	fi
	# Update Pipfile.lock with latest versions
	pipenv update
	# Sync the updated dependencies to requirements files
	$(MAKE) sync-deps
	@echo "Dependencies updated and synchronized!"
