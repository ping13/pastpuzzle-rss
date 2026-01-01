.PHONY: help create-feed test publish clean check quiz token
.PHONY: token

help:
	@echo "Targets:"
	@echo "  help  Show this help"
	@echo "  create-feed  Run the daily scrape, archive update, and feed generation"
	@echo "  test  Install test deps and run pytest"
	@echo "  publish  Copy data/feed.xml to PUBLISH_DIR"
	@echo "  check  Verify the puzzle endpoint is reachable (no archive/feed writes)"
	@echo "  token  Refresh auth token and persist to .env (requires PASTPUZZLE_USER/PASS)"
	@echo "  quiz  Enrich archive by quiz ID (set QUIZ_ID and optional QUIZ_DATE)"
	@echo "  clean  Remove build outputs"

create-feed:
	uv run python -m src.main

test:
	uv sync --group test
	uv run pytest

check:
	uv run python -m src.main --check --pretty-json

token:
	uv run python -m src.get_token --write-env

quiz:
	@if [ -z "$$QUIZ_ID" ]; then \
		echo "QUIZ_ID is required (e.g. make quiz QUIZ_ID=229)"; \
		exit 1; \
	fi; \
	if [ -n "$$QUIZ_DATE" ]; then \
		uv run python -m src.main --quiz-id "$$QUIZ_ID" --quiz-date "$$QUIZ_DATE"; \
	else \
		uv run python -m src.main --quiz-id "$$QUIZ_ID"; \
	fi

publish: create-feed
	@PUBLISH_DIR_VALUE="$$PUBLISH_DIR"; \
	if [ -z "$$PUBLISH_DIR_VALUE" ] && [ -f .env ]; then \
		PUBLISH_DIR_VALUE=$$(awk -F= '/^PUBLISH_DIR=/{sub(/^PUBLISH_DIR=/,"");print;exit}' .env | sed 's/^\"//;s/\"$$//'); \
	fi; \
	if [ -z "$$PUBLISH_DIR_VALUE" ]; then \
		echo "PUBLISH_DIR is not set"; \
		exit 1; \
	fi; \
	mkdir -p "$$PUBLISH_DIR_VALUE"; \
	cp data/feed.xml "$$PUBLISH_DIR_VALUE/"; \
	if [ -f docs/cover.png ]; then \
		cp docs/cover.png "$$PUBLISH_DIR_VALUE/"; \
	fi

clean:
	@rm -f data/feed.xml
