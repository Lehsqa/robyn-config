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


# *************************************************
# ********** tests **********
# *************************************************

.PHONY: tests  # run all tests
tests:
	uv run pytest -vv

.PHONY: tests.coverage  # run all tests with coverage
tests.coverage:
	uv run pytest --cov=./src/app --cov-report=term-missing --cov-report=html

.PHONY: tests.create  # create new service
tests.create:
	robyn-config create my-service --orm sqlalchemy --design ddd ./my-service
	robyn-config add product ./my-service
	robyn-config adminpanel ./my-service
	cd my-service && make makemigration
	cd my-service && cp .env.example .env
	cd my-service && docker compose up -d

.PHONY: tests.delete  # delete service
tests.delete:
	cd my-service && docker compose down -v
	rm -rf my-service

# *************************************************
# ********** code quality **********
# *************************************************

.PHONY: fix  # fix formatting and order imports
fix:
	uv run black src
	uv run ruff check src --fix

.PHONY: check.types  # check type annotations
check.types:
	uv run mypy --check-untyped-defs src

.PHONY: check  # run all checks
check:
	uv run ruff check src
	uv run black --check src
	uv run mypy --check-untyped-defs src
	uv run pytest
