# Contributing to robyn-config

Thanks for taking the time to contribute! This guide keeps PRs fast and predictable.

## Prerequisites
- Python >=3.11,<4.0
- One package manager: `uv` (default) or `pip`
- GNU Make (for convenience)

## Setup
```bash
git clone https://github.com/Lehsqa/robyn-config.git
cd robyn-config
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Development workflow
- Branch from `main` and open PRs against it.
- Keep changes small and focused; include context in commit messages.
- When altering scaffolding, update both templates and related tests.

## Testing
Run fast unit tests:
```bash
python -m pytest tests/unit
```
Run integration tests (uses fake package manager stubs, no network):
```bash
python -m pytest tests/integration
```
If you only touched the `create`/`add` commands, run the targeted integration suites above. Fix or skip coverage warnings only if necessary; avoid relaxing assertions.

## Style & linting
- Follow existing patterns and keep code/comment tone concise.
- Black/ruff/mypy are configured; use `make check` or run tools individually (`ruff check`, `black --check`, `mypy`).
- Templates live in `src/create/common` and `src/add`; prefer Jinja2 changes that remain readable in rendered output.

## Documentation
- Update README.md when CLI flags or behaviors change (e.g., package manager defaults, add-path overrides).
- Keep CHANGELOG.md in sync for user-facing changes when appropriate.

## Pull requests
- Summarize the problem and solution; link related issues.
- Note any behavior changes or migration steps.
- Include test results in the PR description.

Thanks for helping improve robyn-config!
