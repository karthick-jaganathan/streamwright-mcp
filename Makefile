# /*************************************************************************
# * Copyright 2026 Karthick Jaganathan
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# * https://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# **************************************************************************/

# StreamWright MCP - development targets
PACKAGE_NAME = streamwright-mcp
# The Python whose environment the targets use (an active pyenv / virtualenv by default)
PYTHON ?= python
# RUFF=path/to/ruff to use another ruff
RUFF ?= ruff
# Installation mode (dev, prod, dist); FORCE_DEPS=true reinstalls dependencies
MODE ?= prod
FORCE_DEPS ?= false
DIST_DIR ?= /tmp/sdist/streamwright-mcp

PIP_FORCE := $(if $(filter true,$(FORCE_DEPS)),--force-reinstall,)

.PHONY: help install uninstall build clean clean-dist verify lint check-docs test docs

help:
	@echo "StreamWright MCP - Available commands:"
	@echo ""
	@echo "  make install [MODE=dev|prod|dist] - Install $(PACKAGE_NAME) (default: prod; FORCE_DEPS=true)"
	@echo "  make uninstall                    - Uninstall $(PACKAGE_NAME)"
	@echo "  make build                        - Build distribution packages into $(DIST_DIR)"
	@echo "  make clean                        - Clean build and test artifacts"
	@echo "  make clean-dist                   - Clean the distribution directory"
	@echo "  make verify                       - Verify the installation"
	@echo "  make lint                         - Check the code standards: ruff (ruff.toml) + scripts/check_code_standards.py"
	@echo "  make check-docs                   - Check the generated tool reference (docs/mcp.md) is current"
	@echo "  make test                         - Lint and check-docs, then run the tests (pytest)"
	@echo "  make docs                         - Regenerate the tool reference of README.md and docs/mcp.md"
	@echo ""
	@echo "Installation modes:"
	@echo "  MODE=dev   - Development mode (pip install -e .)"
	@echo "  MODE=prod  - Production mode (pip install .)"
	@echo "  MODE=dist  - Distribution mode (build + install from $(DIST_DIR))"

install:
ifeq ($(MODE),dev)
	$(PYTHON) -m pip install -e ".[test]" $(PIP_FORCE)
else ifeq ($(MODE),prod)
	$(PYTHON) -m pip install . $(PIP_FORCE)
else ifeq ($(MODE),dist)
	@$(MAKE) build
	$(PYTHON) -m pip install $(PACKAGE_NAME) --find-links $(DIST_DIR) --force-reinstall
else
	@echo "❌ Invalid MODE: $(MODE). Use dev, prod, or dist"
	@exit 1
endif
	@echo "✅ Installation complete!"
	@$(MAKE) verify

uninstall:
	$(PYTHON) -m pip uninstall -y $(PACKAGE_NAME)

build: clean
	@mkdir -p $(DIST_DIR)
	$(PYTHON) -m build --outdir $(DIST_DIR)
	@echo "✅ Build complete: $(DIST_DIR)"

clean:
	find . -type d \( -name "__pycache__" -o -name "*.egg-info" -o -name build -o -name dist -o -name .pytest_cache \
		-o -name .ruff_cache \) -prune -exec rm -rf {} + 2>/dev/null || true

clean-dist:
	@rm -rf $(DIST_DIR)

verify:
	@$(PYTHON) -m pip show $(PACKAGE_NAME) >/dev/null 2>&1 && echo "✅ $(PACKAGE_NAME) is installed!" || echo "❌ $(PACKAGE_NAME) is not installed!"
	@$(PYTHON) -c "import streamwright.mcp.server" 2>/dev/null && echo "✅ streamwright.mcp import works!" || echo "❌ streamwright.mcp import failed!"
	@$(PYTHON) -m streamwright.core.cli mcp --help >/dev/null 2>&1 && echo "✅ streamwright mcp command works!" || echo "❌ streamwright mcp command failed (is streamwright installed?)"

# The code standards (streamwright docs/design/connector-contract.md section 7); blocking.
# scripts/check_code_standards.py is vendored from streamwright: keep it identical (streamwright's CI compares them).
lint:
	$(RUFF) check .
	$(PYTHON) scripts/check_code_standards.py --strict src tests

check-docs:
	$(PYTHON) -m streamwright.mcp.docs --check docs/mcp.md

test: lint check-docs
	$(PYTHON) -m pytest

docs:
	$(PYTHON) -m streamwright.mcp.docs docs/mcp.md
