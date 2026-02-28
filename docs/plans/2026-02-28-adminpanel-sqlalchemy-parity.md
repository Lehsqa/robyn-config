# Admin Panel SQLAlchemy Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a working `adminpanel` scaffold for all generated backend combinations (`ddd/mvc` × `sqlalchemy/tortoise`) with SQLAlchemy-native admin runtime parity and Alembic migration generation.

**Architecture:** Keep shared admin behavior in `core/*` while introducing ORM adapters (`tortoise` + `sqlalchemy`) behind a stable contract. Preserve public API and route/template contracts, and generate ORM-specific wiring/migrations from `adminpanel` command.

**Tech Stack:** Python 3.12, Robyn, Jinja2 templates, SQLAlchemy async ORM, Tortoise ORM, Alembic, pytest integration tests.

---

### Task 1: Add matrix integration test coverage for `adminpanel`

**Files:**
- Create: `tests/integration/test_adminpanel_command.py`
- Reuse helpers from: `tests/integration/test_create_command.py`

**Step 1: Write the failing test**

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.test_create_command import create_fake_package_managers

ROOT = Path(__file__).resolve().parents[2]
COMBINATIONS = [
    ("ddd", "sqlalchemy"),
    ("ddd", "tortoise"),
    ("mvc", "sqlalchemy"),
    ("mvc", "tortoise"),
]


def run_cli_create(destination: Path, design: str, orm: str, bin_dir: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "create",
            "admin-app",
            "--orm",
            orm,
            "--design",
            design,
            str(destination),
        ],
        check=True,
        env=env,
    )


def run_cli_adminpanel(project_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "cli", "adminpanel", str(project_path)],
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_adminpanel_command_scaffolds_for_all_design_and_orm_combinations(
    tmp_path: Path, design: str, orm: str
) -> None:
    project_dir = tmp_path / f"{design}-{orm}-admin"
    fake_bin = create_fake_package_managers(tmp_path)

    run_cli_create(project_dir, design, orm, fake_bin)
    result = run_cli_adminpanel(project_dir)

    assert result.returncode == 0, result.stderr
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_adminpanel_command.py::test_adminpanel_command_scaffolds_for_all_design_and_orm_combinations -v`
Expected: FAIL on SQLAlchemy cases with current Tortoise-only guard/import assumptions.

**Step 3: Write minimal implementation**

No implementation in this task; this defines red baseline for next tasks.

**Step 4: Run test to verify it still fails for the right reason**

Run: same command as Step 2
Expected: FAIL with ORM support gap symptoms (not syntax/import typos in test).

**Step 5: Commit**

```bash
git add tests/integration/test_adminpanel_command.py
git commit -m "test: add adminpanel matrix integration baseline"
```

### Task 2: Enable `adminpanel` command for both ORMs and pass template context

**Files:**
- Modify: `src/adminpanel/utils.py`

**Step 1: Write the failing test**

Add test in `tests/integration/test_adminpanel_command.py` asserting SQLAlchemy case no longer errors with unsupported ORM message.

```python
assert "requires a Tortoise ORM project" not in result.stderr
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_adminpanel_command.py::test_adminpanel_command_scaffolds_for_all_design_and_orm_combinations -v`
Expected: FAIL because `SUPPORTED_ORM` currently rejects SQLAlchemy.

**Step 3: Write minimal implementation**

Update logic:
- Replace `SUPPORTED_ORM = "tortoise"` with `SUPPORTED_ORMS = ("tortoise", "sqlalchemy")`.
- Validate `orm in SUPPORTED_ORMS`.
- Pass `{"design": design, "orm": orm}` into `_render_template_tree(...)`.

**Step 4: Run test to verify it passes initial ORM gate**

Run: same command as Step 2
Expected: SQLAlchemy no longer fails at unsupported ORM guard; later template/runtime assumptions may still fail.

**Step 5: Commit**

```bash
git add src/adminpanel/utils.py tests/integration/test_adminpanel_command.py
git commit -m "feat: allow adminpanel scaffolding for sqlalchemy projects"
```

### Task 3: Add ORM-specific admin bootstrap template wiring

**Files:**
- Modify: `src/adminpanel/template/__init__.py.jinja2`

**Step 1: Write the failing test**

Extend integration test to assert generated bootstrap imports ORM-specific sources:
- Tortoise: uses `TORTOISE_ORM` / `MODEL_MODULES`.
- SQLAlchemy: uses SQLAlchemy engine/session modules and no `TORTOISE_ORM` import.

```python
admin_init = (admin_dir / "__init__.py").read_text()
if orm == "sqlalchemy":
    assert "TORTOISE_ORM" not in admin_init
    assert "sqlalchemy" in admin_init.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_adminpanel_command.py -v`
Expected: FAIL on SQLAlchemy bootstrap assertions.

**Step 3: Write minimal implementation**

Template update:
- Add Jinja branches for `orm == "sqlalchemy"` and `orm == "tortoise"`.
- Keep exported API unchanged: `register(app) -> AdminSite`.
- For SQLAlchemy branch, inject adapter selection/startup dependencies without changing caller contract.

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_adminpanel_command.py -v`
Expected: bootstrap assertions pass; runtime CRUD may still fail.

**Step 5: Commit**

```bash
git add src/adminpanel/template/__init__.py.jinja2 tests/integration/test_adminpanel_command.py
git commit -m "feat: render orm-specific admin bootstrap wiring"
```

### Task 4: Introduce adapter contract and adapter resolution

**Files:**
- Modify: `src/adminpanel/template/orm/base.py`
- Modify: `src/adminpanel/template/orm/tortoise.py`
- Create: `src/adminpanel/template/orm/sqlalchemy.py`
- Create: `src/adminpanel/template/orm/__init__.py`

**Step 1: Write the failing test**

Create unit tests in `tests/unit/test_adminpanel_orm_adapter_contract.py` validating:
- Contract methods exist on both adapters.
- Adapter resolution returns correct class by configured ORM key.

```python
def test_resolve_adapter_sqlalchemy():
    adapter = resolve_adapter("sqlalchemy")
    assert adapter.__class__.__name__ == "SQLAlchemyAdapter"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_adminpanel_orm_adapter_contract.py -v`
Expected: FAIL because resolver/SQLAlchemy adapter missing.

**Step 3: Write minimal implementation**

- Expand base adapter contract with metadata/query/object methods consumed by core.
- Add resolver function in `orm/__init__.py`.
- Implement minimal SQLAlchemy adapter with async session-based CRUD/query primitives.
- Preserve Tortoise adapter behavior under same interface.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_adminpanel_orm_adapter_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/adminpanel/template/orm/base.py src/adminpanel/template/orm/tortoise.py src/adminpanel/template/orm/sqlalchemy.py src/adminpanel/template/orm/__init__.py tests/unit/test_adminpanel_orm_adapter_contract.py
git commit -m "feat: add adminpanel orm adapter contract and resolver"
```

### Task 5: Refactor `ModelAdmin` and field/filter logic to adapter APIs

**Files:**
- Modify: `src/adminpanel/template/core/admin.py`
- Modify: `src/adminpanel/template/core/fields.py`
- Modify: `src/adminpanel/template/core/filters.py`
- Modify: `src/adminpanel/template/core/inline.py`

**Step 1: Write the failing test**

Add tests in `tests/unit/test_adminpanel_core_adapter_usage.py`:
- Ensure `ModelAdmin.get_queryset` delegates to adapter query builder.
- Ensure field metadata is resolved via adapter methods, not direct Tortoise `_meta` reads.

```python
async def test_model_admin_uses_adapter_metadata(fake_adapter, fake_model):
    admin = ModelAdmin(fake_model, orm_adapter=fake_adapter)
    assert admin.table_fields
    assert fake_adapter.get_model_fields.called
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_adminpanel_core_adapter_usage.py -v`
Expected: FAIL due direct Tortoise-coupled internals.

**Step 3: Write minimal implementation**

- Inject adapter into `ModelAdmin` (default from site-level resolver).
- Replace `tortoise.fields`/`_meta.fields_map` assumptions with adapter metadata helpers.
- Keep existing external class names/method signatures usable.

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_adminpanel_core_adapter_usage.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/adminpanel/template/core/admin.py src/adminpanel/template/core/fields.py src/adminpanel/template/core/filters.py src/adminpanel/template/core/inline.py tests/unit/test_adminpanel_core_adapter_usage.py
git commit -m "refactor: move model admin metadata and query logic behind orm adapter"
```

### Task 6: Refactor `AdminSite` runtime flow to adapter/session lifecycle

**Files:**
- Modify: `src/adminpanel/template/core/site.py`
- Modify: `src/adminpanel/template/core/__init__.py`
- Modify: `src/adminpanel/template/auth_models.py`
- Modify: `src/adminpanel/template/models.py`

**Step 1: Write the failing test**

Extend integration tests to assert runtime startup for SQLAlchemy scaffolds does not import/use Tortoise globals and admin auth endpoints are available.

```python
assert "from tortoise" not in admin_site_source_for_sqlalchemy
```

Add endpoint smoke check (subprocess app run or docker-backed smoke helper) for `/admin/login` returning 200/307.

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_adminpanel_command.py -v`
Expected: FAIL on SQLAlchemy runtime path.

**Step 3: Write minimal implementation**

- Site-level adapter selection during `AdminSite` init.
- Startup hooks call adapter lifecycle init methods.
- Replace direct `Tortoise` cleanup/init flows with adapter abstractions.
- Keep auth/session contracts and route URLs unchanged.

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_adminpanel_command.py -v`
Expected: SQLAlchemy runtime smoke now passes.

**Step 5: Commit**

```bash
git add src/adminpanel/template/core/site.py src/adminpanel/template/core/__init__.py src/adminpanel/template/auth_models.py src/adminpanel/template/models.py tests/integration/test_adminpanel_command.py
git commit -m "feat: make admin site runtime orm-agnostic via adapter lifecycle"
```

### Task 7: Generate SQLAlchemy Alembic migration for admin tables

**Files:**
- Modify: `src/adminpanel/utils.py`
- Create: `src/adminpanel/template/migrations/sqlalchemy/adminpanel_revision.py.jinja2`

**Step 1: Write the failing test**

Add integration test in `tests/integration/test_adminpanel_command.py` for SQLAlchemy combos:
- Assert one new admin migration file appears in expected `versions` directory.
- Assert file contains `robyn_admin_users` create statements.

```python
versions_dir = project_dir / expected_versions_relpath
revisions = list(versions_dir.glob("*_adminpanel*.py"))
assert revisions
assert "robyn_admin_users" in revisions[0].read_text()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_adminpanel_command.py::test_adminpanel_command_scaffolds_for_all_design_and_orm_combinations -v`
Expected: FAIL because migration generation is missing.

**Step 3: Write minimal implementation**

- Add helper in `adminpanel/utils.py` to locate SQLAlchemy Alembic `versions` path by design.
- Detect latest existing revision for `down_revision`.
- Render migration template with deterministic revision ID and timestamped filename.

**Step 4: Run test to verify it passes**

Run: same command as Step 2
Expected: PASS with migration file created and linked.

**Step 5: Commit**

```bash
git add src/adminpanel/utils.py src/adminpanel/template/migrations/sqlalchemy/adminpanel_revision.py.jinja2 tests/integration/test_adminpanel_command.py
git commit -m "feat: generate admin alembic migration for sqlalchemy projects"
```

### Task 8: Preserve and verify full parity behavior across all combinations

**Files:**
- Modify: `tests/integration/test_adminpanel_command.py`
- Optionally modify: `tests/integration/test_app_end_to_end.py`

**Step 1: Write the failing test**

Add parity assertions for all combinations:
- Generated admin package contains expected core/template files.
- Server wiring includes `adminpanel.register(...)` call.
- `/admin/login` reachable and at least one model route renders.

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_adminpanel_command.py -v`
Expected: FAIL where parity still incomplete.

**Step 3: Write minimal implementation**

Fill remaining parity gaps discovered by tests (route registration edge cases, template context mismatch, adapter method holes).

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_adminpanel_command.py -v`
Expected: PASS across all 4 combinations.

**Step 5: Commit**

```bash
git add tests/integration/test_adminpanel_command.py tests/integration/test_app_end_to_end.py src/adminpanel
# add specific changed files if preferred
git commit -m "test: verify adminpanel parity across all orm/design combinations"
```

### Task 9: Full verification before completion

**Files:**
- Modify as needed from previous tasks only

**Step 1: Run focused unit + integration checks**

Run:
- `pytest tests/unit/test_adminpanel_orm_adapter_contract.py -v`
- `pytest tests/unit/test_adminpanel_core_adapter_usage.py -v`
- `pytest tests/integration/test_adminpanel_command.py -v`

Expected: all PASS.

**Step 2: Run broader regression suite**

Run:
- `pytest tests/integration/test_create_command.py -v`
- `pytest tests/integration/test_add_command.py -v`

Expected: PASS (no regressions to create/add workflows).

**Step 3: Lint changed files**

Run: `ruff check src/adminpanel tests/integration/test_adminpanel_command.py tests/unit/test_adminpanel_orm_adapter_contract.py tests/unit/test_adminpanel_core_adapter_usage.py`
Expected: PASS (no violations).

**Step 4: Final commit (if any unstaged fixes from verification)**

```bash
git add <changed-files>
git commit -m "fix: address adminpanel verification issues"
```

**Step 5: Produce completion report with evidence**

Include exact command outputs summary (pass counts, failed=0), list of changed files, and known follow-ups (if any).
