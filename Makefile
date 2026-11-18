TEST_DB_PORT ?= 55432
export TEST_DATABASE_URL ?= postgresql+asyncpg://postgres:postgres@localhost:$(TEST_DB_PORT)/postgres

.PHONY: dev down test testdb lint fmt logs

dev:            ## run the whole system (db, api, worker+scheduler)
	docker compose up --build

down:
	docker compose down

testdb:         ## throwaway Postgres for tests
	docker start hotelpilot-testdb 2>/dev/null || docker run -d --name hotelpilot-testdb \
		-e POSTGRES_PASSWORD=postgres -p $(TEST_DB_PORT):5432 postgres:17-alpine
	uv run python scripts/wait_db.py

test: testdb
	uv run pytest -q

lint:
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
	uv run mypy

fmt:
	uv run ruff format src tests scripts
	uv run ruff check --fix src tests scripts

logs:
	docker compose logs -f --tail=100
