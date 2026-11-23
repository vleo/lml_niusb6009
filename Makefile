# Makefile for lml_common_toplevel
.PHONY: all venv install build dev-install clean distclean

# Default python interpreter (can be overridden from command line)
PYTHON ?= python3
VENV_DIR = .venv
VENV_BIN = $(VENV_DIR)/bin

# Use env/CLI WHEELHOUSE if set; otherwise auto-detect ./wheelhouse if it exists
WHEELHOUSE ?= $(wildcard wheelhouse)

ifneq ($(strip $(WHEELHOUSE)),)
  PIP_FLAGS = --no-index --find-links=$(WHEELHOUSE)
else
  PIP_FLAGS =
endif

# Default target runs the full setup
all: venv dev-install build 

# 1. Initialize the virtual environment and upgrade pip
venv: $(VENV_BIN)/activate

$(VENV_BIN)/activate:
	@echo "==> Creating virtual environment..."
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_BIN)/pip install $(PIP_FLAGS) --upgrade pip pip setuptools setuptools-scm wheel build
	@touch $(VENV_BIN)/activate

# 2. Install the package in editable mode with development tools
dev-install: venv
	@echo "==> Installing package in editable mode with dev tools..."
	$(VENV_BIN)/pip install $(PIP_FLAGS) --no-build-isolation -e ".[dev]"

# 3. Clean and build standard distribution wheel and sdist packages
build: venv
	@echo "==> Building production artifacts..."
	@rm -rf dist/
	$(VENV_BIN)/python -m build --no-isolation

# 4. Bundle all build, runtime, and [dev] wheels for offline transfer
wheelhouse: venv
	@echo "==> Downloading offline wheelhouse..."
	@$(MAKE) distclean
	@$(MAKE) venv
	@mkdir -p wheelhouse
	$(VENV_BIN)/pip download -d wheelhouse pip setuptools setuptools-scm wheel build
	$(VENV_BIN)/pip download -d wheelhouse --no-build-isolation ".[dev]"
	@rm -f wheelhouse/lml_niusb6009-*.whl

# 4. Run your verification test suite
#test: venv
#	@echo "==> Running validation tests..."
#	$(VENV_BIN)/python tests/test_both.py

# 5. Scrub all generated build artifacts, caches, and binaries
clean:
	@echo "==> Cleaning generated build files and caches..."
	rm -rf build/ dist/ *.egg-info src/*.egg-info PKG-INFO setup.cfg
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# 6. Deep clean including removing the virtual environment entirely
distclean: clean
	@echo "==> Removing virtual environment..."
	rm -rf $(VENV_DIR) wheelhouse/
