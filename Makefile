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
	robyn-config create service_test --orm sqlalchemy --design ddd ./service_test --uid sparkid
	robyn-config add product ./service_test
	robyn-config adminpanel ./service_test
	cd service_test && make makemigration
	cd service_test && cp .env.example .env
	cd service_test && docker compose up -d

.PHONY: tests.delete  # delete service
tests.delete:
	cd service_test && docker compose down -v
	rm -rf service_test

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
