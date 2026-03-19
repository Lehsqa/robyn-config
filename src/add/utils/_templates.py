"""Template rendering and scaffolding for the 'add' command."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from ._paths import DDDAddPaths, MVCAddPaths

ADD_MODULE_ROOT = Path(__file__).resolve().parent.parent
JINJA_ENV = Environment(undefined=StrictUndefined)


def _render_template_file(
    source: Path, target: Path, context: dict[str, str]
) -> None:
    """Render a Jinja2 template file to target location."""
    template_content = source.read_text()
    template = JINJA_ENV.from_string(template_content)
    rendered = template.render(**context)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)


def _render_template_string(template_str: str, context: dict[str, str]) -> str:
    """Render a Jinja2 template string."""
    template = JINJA_ENV.from_string(template_str)
    return template.render(**context)


def _render_templates_from_directory(
    template_dir: Path,
    target_dir: Path,
    context: dict[str, str],
    project_root: Path,
    created_files: list[str],
) -> None:
    """Render all Jinja2 templates in a directory to the target directory."""
    for template_file in template_dir.glob("*.jinja2"):
        target_path = target_dir / template_file.stem
        _render_template_file(template_file, target_path, context)
        created_files.append(str(target_path.relative_to(project_root)))


def _add_ddd_templates(
    project_path: Path,
    paths: DDDAddPaths,
    name: str,
    name_capitalized: str,
    orm: str,
) -> list[str]:
    """Add DDD templates to the project."""
    from ._injection import (
        _add_table_to_module_package,
        _add_table_to_tables_py,
        _ensure_import_from,
        _register_routes_ddd,
        _update_init_file,
    )

    templates_path = ADD_MODULE_ROOT / "ddd"
    created_files = []

    context = {
        "name": name,
        "Name": name_capitalized,
        "orm": orm,
    }

    # Domain layer
    domain_dir = paths.domain / name
    domain_templates = templates_path / "domain" / "__name__"
    _render_templates_from_directory(
        domain_templates, domain_dir, context, project_path, created_files
    )

    # Update domain __init__.py
    domain_init = paths.domain / "__init__.py"
    _ensure_import_from(
        domain_init, ".", name, trailing_comment="# noqa: F401"
    )

    # Add table model
    table_class_name = f"{name_capitalized}Table"
    table_template = (
        templates_path / "infrastructure" / orm / "__name___table.py.jinja2"
    )
    table_module_file = _add_table_to_module_package(
        paths.db_tables,
        table_template,
        module_name=name,
        table_class_name=table_class_name,
        context=context,
    )
    if table_module_file:
        created_files.append(str(table_module_file.relative_to(project_path)))
    else:
        # Legacy projects still using tables.py
        _add_table_to_tables_py(
            paths.db_tables,
            name,
            name_capitalized,
            orm,
            context,
        )

    # Infrastructure repository
    repo_template = (
        templates_path
        / "infrastructure"
        / orm
        / "repository"
        / "__name__.py.jinja2"
    )
    if repo_template.exists():
        repo_target = paths.db_repository / f"{name}.py"
        _render_template_file(repo_template, repo_target, context)
        created_files.append(str(repo_target.relative_to(project_path)))

        # Update repository __init__.py
        repo_init = paths.db_repository / "__init__.py"
        _update_init_file(
            repo_init,
            f"from .{name} import {name_capitalized}Repository  # noqa: F401",
            f"{name_capitalized}Repository",
        )

    # Operational layer
    ops_template = templates_path / "operational" / "__name__.py.jinja2"
    if ops_template.exists():
        ops_target = paths.operational / f"{name}.py"
        _render_template_file(ops_template, ops_target, context)
        created_files.append(str(ops_target.relative_to(project_path)))

        # Update operational __init__.py
        ops_init = paths.operational / "__init__.py"
        _ensure_import_from(
            ops_init, ".", name, trailing_comment="# noqa: F401"
        )

    # Presentation layer
    pres_dir = paths.presentation / name
    pres_templates = templates_path / "presentation" / "__name__"
    _render_templates_from_directory(
        pres_templates, pres_dir, context, project_path, created_files
    )

    # Auto-register routes in presentation/__init__.py
    _register_routes_ddd(paths.presentation, name)

    return created_files


def _add_mvc_templates(
    project_path: Path,
    paths: MVCAddPaths,
    name: str,
    name_capitalized: str,
    orm: str,
) -> list[str]:
    """Add MVC templates to the project."""
    from ._injection import (
        _add_table_to_module_package,
        _add_to_all_list,
        _append_class_to_file,
        _ensure_import_from,
        _register_routes_mvc,
        _update_init_file,
    )

    templates_path = ADD_MODULE_ROOT / "mvc"
    created_files = []

    context = {
        "name": name,
        "Name": name_capitalized,
        "orm": orm,
    }

    # Models layer
    models_file = paths.db_tables
    repo_file = paths.db_repository

    # 1. Add table model
    table_class = f"{name_capitalized}Table"
    if models_file.name == "__init__.py":
        table_template = (
            templates_path / "models" / orm / "table_module.py.jinja2"
        )
        table_module_file = _add_table_to_module_package(
            models_file,
            table_template,
            module_name=name,
            table_class_name=table_class,
            context=context,
        )
        if table_module_file:
            created_files.append(
                str(table_module_file.relative_to(project_path))
            )
    else:
        table_template = templates_path / "models" / orm / "table.py.jinja2"
        if models_file.exists() and table_template.exists():
            _append_class_to_file(
                models_file, table_template, context, table_class
            )
            _add_to_all_list(models_file, table_class)
            created_files.append(str(models_file.relative_to(project_path)))

    # 2. Append Repository to repository.py
    repo_template = templates_path / "models" / orm / "repository.py.jinja2"
    repo_class = f"{name_capitalized}Repository"
    if repo_file.exists() and repo_template.exists():
        table_import_module = (
            ".tables" if models_file.name == "__init__.py" else ".models"
        )
        _ensure_import_from(repo_file, table_import_module, table_class)

        _append_class_to_file(repo_file, repo_template, context, repo_class)
        created_files.append(str(repo_file.relative_to(project_path)))

        # Update app models __init__.py to export repository
        if models_file.name == "__init__.py":
            models_init = models_file.parent.parent / "__init__.py"
        else:
            models_init = models_file.parent / "__init__.py"
        _update_init_file(
            models_init,
            f"from .repository import {repo_class}  # noqa: F401",
            repo_class,
        )

    # Views layer
    views_template = templates_path / "views" / "__name__.py.jinja2"
    if views_template.exists():
        views_target = paths.views / f"{name}.py"
        _render_template_file(views_template, views_target, context)
        created_files.append(str(views_target.relative_to(project_path)))

        # Update views __init__.py
        views_init = paths.views / "__init__.py"
        _update_init_file(
            views_init,
            f"from .{name} import register as register_{name}  # noqa: F401",
            f"register_{name}",
        )

    # Auto-register routes in urls.py
    _register_routes_mvc(paths.urls, name)

    return created_files
