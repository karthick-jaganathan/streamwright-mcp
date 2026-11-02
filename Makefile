# StreamWright MCP - development targets
PYTHON ?= python
# RUFF=path/to/ruff to use another ruff
RUFF ?= ruff

.PHONY: help lint test docs

help:
	@echo "StreamWright MCP - Available commands:"
	@echo ""
	@echo "  make lint    - Check the code standards: ruff (ruff.toml) + scripts/check_code_standards.py"
	@echo "  make test    - Lint, then run the tests (pytest)"
	@echo "  make docs    - Regenerate the tool reference of README.md and docs/mcp.md"

# The code standards (streamwright docs/design/connector-contract.md section 7); blocking.
# scripts/check_code_standards.py is vendored from streamwright: keep it identical (streamwright's CI compares them).
lint:
	$(RUFF) check .
	$(PYTHON) scripts/check_code_standards.py --strict src tests

test: lint
	$(PYTHON) -m pytest

docs:
	$(PYTHON) -m streamwright.mcp.docs docs/mcp.md
