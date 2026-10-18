# Makefile for lml_common_toplevel
.PHONY: all venv install build dev-install test clean

# Default python interpreter (can be overridden from command line)
PYTHON ?= python3
VENV_DIR = .venv
VENV_BIN = $(VENV_DIR)/bin

PIP_FIND_LINKS = /home/vleo/00_HW/CODES_U/lml_common/dist

# Default target runs the full setup and tests
all: venv dev-install build test

# 1. Initialize the virtual environment and upgrade pip
venv: $(VENV_BIN)/activate

$(VENV_BIN)/activate:
	@echo "==> Creating virtual environment..."
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_BIN)/pip install --upgrade pip
	@touch $(VENV_BIN)/activate

# 2. Install the package in editable mode with development tools
dev-install: venv
	@echo "==> Installing package in editable mode with dev tools..."
	$(VENV_BIN)/pip install --find-links=$(PIP_FIND_LINKS) -e ".[dev]"

# 3. Clean and build standard distribution wheel and sdist packages
build: venv
	@echo "==> Building production artifacts..."
	@rm -rf dist/
	$(VENV_BIN)/pip install build
	$(VENV_BIN)/python -m build

# 4. Run your verification test suite
test: venv
	@echo "==> Running validation tests..."
	$(VENV_BIN)/python tests/test_both.py

# 5. Scrub all generated build artifacts, caches, and binaries
clean:
	@echo "==> Cleaning generated build files and caches..."
	rm -rf build/ dist/ *.egg-info src/*.egg-info src/lml_common/*.egg-info
	rm -rf src/lml_common/*.c src/lml_common/*.so src/lml_common/*.pyd
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# 6. Deep clean including removing the virtual environment entirely
distclean: clean
	@echo "==> Removing virtual environment..."
	rm -rf $(VENV_DIR)
