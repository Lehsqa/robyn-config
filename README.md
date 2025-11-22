# robyn-config

`robyn-config` is a small CLI that scaffolds Robyn backend projects from the bundled templates. It can generate either DDD or MVC layouts and swaps between SQLAlchemy and Tortoise implementations on demand.

## Installation

```bash
pip install .
# or
uv tool install .
```

## Usage

Create a project with your preferred ORM and architecture:

```bash
robyn-config create --orm sqlalchemy --design ddd ./my-service
robyn-config create --orm tortoise --design mvc ~/projects/newsletter
```

Options:

- `--orm` (`sqlalchemy`|`tortoise`) selects the database layer.
- `--design` (`ddd`|`mvc`) toggles between the Domain-Driven and MVC templates.
- `destination` is the target directory (defaults to `.`) and must be empty.

The command copies:

- Common project files (docker-compose, Makefile, env templates, README, pyproject, uv.lock).
- Application code from `src/app_ddd` or `src/app_mvc` into `src/app`.
- Compose helpers from `src/common/compose/app` with ORM-specific dev/prod runners.
- For Tortoise projects, Alembic artifacts are omitted from the Docker image.

## Template contents

The shipped templates live alongside the CLI:

- Root-level files sit under `src/common`.
- Compose files are under `src/common/compose/app`.
- Application code is under `src/ddd` and `src/mvc`.

Feel free to modify these in-place to customize the generated projects.

## Development

Run the linters/tests locally:

```bash
uv venv && source .venv/bin/activate
uv pip install -e .[dev]
ruff check src
pytest
```

Build a wheel for distribution:

```bash
python -m build
```
