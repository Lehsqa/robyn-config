# ************************************************
# ********** setup **********
# ************************************************
.PHONY: install  # install production dependencies
install:
	uv pip install -e .

.PHONY: install.dev  # install development dependencies
install.dev:
	uv pip install -e ".[dev]"

.PHONY: sync  # sync all dependencies with uv
sync:
	uv sync

.PHONY: lock  # lock dependencies
lock:
	uv lock


# ************************************************
# ********** migrations **********
# ************************************************
MIGRATION_MESSAGE ?= "automated migration"

{%- if orm == "sqlalchemy" %}

.PHONY: makemigration
makemigration:
	uv run alembic revision --autogenerate -m $(MIGRATION_MESSAGE)

.PHONY: migrate
migrate:
	uv run alembic upgrade head
{%- elif orm == "tortoise" %}

.PHONY: makemigration
makemigration:
	uv run aerich migrate --name $(MIGRATION_MESSAGE) --offline

.PHONY: migrate
migrate:
	uv run aerich upgrade
{%- endif %}


# ************************************************
# ********** application **********
# ************************************************

.PHONY: run  # run the application in production mode
run:
	uv run -- python -m app.server --fast --log-level WARNING

.PHONY: run.dev  # run the application in development mode
run.dev:
	uv run -- python -m robyn src/app/server.py --dev

.PHONY: run.compose  # run the entire compose stack
run.compose:
	docker compose up --build


# *************************************************
# ********** tests **********
# *************************************************

.PHONY: tests  # run all tests
tests:
	uv run pytest

.PHONY: tests.coverage  # run all tests with coverage
tests.coverage:
	uv run pytest --cov=./src/app --cov-report=term-missing --cov-report=html


# *************************************************
# ********** code quality **********
# *************************************************

.PHONY: fix  # fix formatting and order imports
fix:
	uv run black src/app
	uv run isort src
	uv run ruff check src/app --fix

.PHONY: check.types  # check type annotations
check.types:
	uv run mypy --check-untyped-defs src/app

.PHONY: check  # run all checks
check:
	uv run ruff check src/app
	uv run black --check src/app
	uv run isort --check src
	uv run mypy --check-untyped-defs src/app
	uv run pytest


# *************************************************
# ********** docker helpers **********
# *************************************************
.PHONY: backend.run
backend.run:
	docker compose up -d app

.PHONY: backend.status
backend.status:
	docker compose logs --tail 100 app

.PHONY: backend.update
backend.update:
	docker compose build --no-cache app

.PHONY: backend.stop
backend.stop:
	docker compose down
