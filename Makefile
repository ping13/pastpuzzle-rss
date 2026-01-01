.PHONY: help run test publish clean check

help:
	@echo "Targets:"
	@echo "  help  Show this help"
	@echo "  run   Run the daily scrape, archive update, and feed generation"
	@echo "  test  Install test deps and run pytest"
	@echo "  publish  Copy data/feed.xml to PUBLISH_DIR"
	@echo "  check  Verify the puzzle endpoint is reachable (no archive/feed writes)"
	@echo "  clean  Remove build outputs"

run:
	uv run python -m src.main

test:
	uv sync --group test
	uv run pytest

check:
	uv run python -m src.main --check --pretty-json

publish: run
	@PUBLISH_DIR_VALUE="$$PUBLISH_DIR"; \
	if [ -z "$$PUBLISH_DIR_VALUE" ] && [ -f .env ]; then \
		PUBLISH_DIR_VALUE=$$(awk -F= '/^PUBLISH_DIR=/{sub(/^PUBLISH_DIR=/,"");print;exit}' .env | sed 's/^\"//;s/\"$$//'); \
	fi; \
	if [ -z "$$PUBLISH_DIR_VALUE" ]; then \
		echo "PUBLISH_DIR is not set"; \
		exit 1; \
	fi; \
	mkdir -p "$$PUBLISH_DIR_VALUE"; \
	cp data/feed.xml "$$PUBLISH_DIR_VALUE/"

clean:
	@rm -f data/feed.xml
