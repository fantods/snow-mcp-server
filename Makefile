.PHONY: install dev test run clean

install:
	uv sync

dev:
	uv run mcp dev src/snow/server.py

test:
	uv run pytest tests/ -v

run:
	uv run python -m snow.server

clean:
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
