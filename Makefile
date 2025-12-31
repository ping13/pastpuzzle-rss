.PHONY: help run test

help:
	@echo "Targets:"
	@echo "  help  Show this help"
	@echo "  run   Run the daily scrape, archive update, and feed generation"
	@echo "  test  Install test deps and run pytest"

run:
	uv run python -m src.main

test:
	uv sync --group test
	uv run pytest
