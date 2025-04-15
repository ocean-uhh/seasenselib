.PHONY: clean install test build publish

# Define variables for commands to make them easily changeable
PYTHON := $(shell command -v python3 || command -v python)
PIP := $(shell command -v pip3 || command -v pip)
TWINE := twine

# Default target executed when no arguments are given to make
all: help

help:
	@echo "Please use \`make <target>\` where <target> is one of"
	@echo "  install   to install the package"
	@echo "  test      to run tests"
	@echo "  build     to package the library"
	@echo "  publish   to upload the package to PyPI"
	@echo "  clean     to clean the project directory"

# Clean previous builds and pyc files
clean:
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf build/ dist/ *.egg-info

# Install the package locally
install: clean
	$(PIP) install .

# Run unit tests
test:
	$(PYTHON) -m unittest discover tests/

# Build the package
build: clean
	$(PYTHON) setup.py sdist bdist_wheel

# Publish the package to PyPI
publish:
	$(TWINE) upload dist/*

# Command to setup virtual environment and install dependencies
setup:
	$(PYTHON) -m venv venv
	$(PIP) install -r requirements.txt
