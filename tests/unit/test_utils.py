import pytest
from pathlib import Path
from unittest.mock import patch

from src.create import utils as create_utils
from src.create.utils import _config as create_config
from src.create.utils import _filesystem as create_filesystem
from src.add import utils as add_utils
from src.add.utils import _injection as add_injection
from src.add.utils import _paths as add_paths


# --- Tests for src/create/utils.py ---

def test_collect_common_items(tmp_path):
    """Test that finding common items correctly filters based on ORM."""
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "Makefile").touch()
    (common_dir / "README.md.jinja2").touch()
    (common_dir / "alembic.ini.jinja2").touch()
    (common_dir / "compose").mkdir()
    (common_dir / ".DS_Store").touch()

    with patch("src.create.utils._filesystem.COMMON_DIR", common_dir):
        # SQLAlchemy should include everything (alembic.ini is kept)
        items_sql = create_filesystem._collect_common_items("sqlalchemy", "uv")
        assert Path("Makefile") in items_sql
        assert Path("README.md") in items_sql
        assert Path("alembic.ini") in items_sql
        assert Path("uv.lock") in items_sql
        assert Path("poetry.lock") not in items_sql
        assert Path("compose") not in items_sql
        assert Path(".DS_Store") not in items_sql

        # Tortoise should exclude alembic.ini
        items_tortoise = create_filesystem._collect_common_items(
            "tortoise", "poetry"
        )
        assert Path("Makefile") in items_tortoise
        assert Path("README.md") in items_tortoise
        assert Path("alembic.ini") not in items_tortoise
        assert Path("poetry.lock") in items_tortoise
        assert Path("uv.lock") not in items_tortoise


def test_get_template_config():
    """Test that template config is retrieved correctly."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "mypro", "uv", "none"
    )
    assert config["design"] == "ddd"
    assert config["orm"] == "sqlalchemy"
    assert config["name"] == "mypro"
    assert config["package_manager"] == "uv"
    assert config["uid"] == "none"

    with pytest.raises(SystemExit):
        create_config._get_template_config(
            "invalid", "orm", "proj", "uv", "none"
        )


def test_uid_choices_constant():
    """Test that UID choices include the supported options in fallback order."""
    assert "none" in create_config.UID_CHOICES
    assert "sparkid" in create_config.UID_CHOICES
    assert create_config.UID_CHOICES[0] == "none"


def test_get_template_config_includes_uid():
    """Test that the template context preserves the selected UID type."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "myproj", "uv", "sparkid"
    )
    assert config["uid"] == "sparkid"


def test_get_template_config_uid_defaults_to_none():
    """Test that explicit 'none' flows through the template context unchanged."""
    config = create_config._get_template_config(
        "ddd", "sqlalchemy", "myproj", "uv", "none"
    )
    assert config["uid"] == "none"


def test_render_jinja2_in_tree(tmp_path):
    """_render_jinja2_in_tree renders .jinja2 files and deletes them."""
    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    jinja_file = sub_dir / "base.py.jinja2"
    jinja_file.write_text("id = {{ uid }}")

    create_filesystem._render_jinja2_in_tree(tmp_path, {"uid": "sparkid"})

    rendered = sub_dir / "base.py"
    assert rendered.exists()
    assert rendered.read_text() == "id = sparkid"
    assert not jinja_file.exists()


def test_render_jinja2_in_tree_noop_when_no_templates(tmp_path):
    """_render_jinja2_in_tree is a no-op when no .jinja2 files exist."""
    regular_file = tmp_path / "file.py"
    regular_file.write_text("class Foo: pass")

    create_filesystem._render_jinja2_in_tree(tmp_path, {"uid": "none"})

    assert regular_file.exists()
    assert regular_file.read_text() == "class Foo: pass"


def _generated_base_path(destination: Path, design: str) -> Path:
    if design == "ddd":
        return (
            destination
            / "src"
            / "app"
            / "infrastructure"
            / "database"
            / "tables"
            / "base.py"
        )
    return destination / "src" / "app" / "models" / "tables" / "base.py"


@pytest.mark.parametrize(
    ("design", "orm", "uid", "expected_snippets"),
    [
        ("ddd", "sqlalchemy", "none", ["id: Mapped[int] = mapped_column(primary_key=True)"]),
        ("ddd", "sqlalchemy", "uuidv4", ["from sqlalchemy import Uuid", "default=uuid.uuid4"]),
        ("ddd", "sqlalchemy", "uuidv7", ["from sqlalchemy import Uuid", "default=uuid.uuid7"]),
        ("ddd", "sqlalchemy", "nanoid", ["from nanoid import generate", "String(21)"]),
        ("ddd", "sqlalchemy", "ulid", ["from ulid import ULID", "String(26)"]),
        ("ddd", "sqlalchemy", "sparkid", ["from sparkid import generate_id", "default=generate_id"]),
        ("ddd", "tortoise", "none", ["id = fields.IntField(pk=True)"]),
        ("ddd", "tortoise", "uuidv4", ["id = fields.UUIDField(pk=True)"]),
        ("ddd", "tortoise", "uuidv7", ["import uuid", "default=uuid.uuid7"]),
        ("ddd", "tortoise", "nanoid", ["from nanoid import generate", "max_length=21"]),
        ("ddd", "tortoise", "ulid", ["from ulid import ULID", "max_length=26"]),
        ("ddd", "tortoise", "sparkid", ["from sparkid import generate_id", "default=generate_id"]),
        ("mvc", "sqlalchemy", "sparkid", ["from sparkid import generate_id", "default=generate_id"]),
        ("mvc", "tortoise", "nanoid", ["from nanoid import generate", "max_length=21"]),
    ],
)
def test_copy_template_renders_uid_base_templates(
    tmp_path, design, orm, uid, expected_snippets
):
    destination = tmp_path / f"{design}-{orm}-{uid}"

    create_filesystem.copy_template(
        destination,
        orm,
        design,
        "uid-project",
        "uv",
        uid,
    )

    base_file = _generated_base_path(destination, design)
    content = base_file.read_text()

    assert base_file.exists()
    for snippet in expected_snippets:
        assert snippet in content
    assert not list(destination.rglob("*.jinja2"))


@pytest.mark.parametrize(
    ("package_manager", "uid", "expected_dependency"),
    [
        ("uv", "nanoid", 'python-nanoid>=2.0.0'),
        ("uv", "ulid", 'python-ulid>=3.0.0'),
        ("uv", "sparkid", 'sparkid>=1.0.0'),
        ("poetry", "nanoid", 'python-nanoid = ">=2.0.0"'),
        ("poetry", "ulid", 'python-ulid = ">=3.0.0"'),
        ("poetry", "sparkid", 'sparkid = ">=1.0.0"'),
    ],
)
def test_copy_template_adds_uid_metadata_and_dependencies(
    tmp_path, package_manager, uid, expected_dependency
):
    destination = tmp_path / f"{package_manager}-{uid}"

    create_filesystem.copy_template(
        destination,
        "sqlalchemy",
        "ddd",
        "uid-project",
        package_manager,
        uid,
    )

    pyproject_content = (destination / "pyproject.toml").read_text()

    assert f'uid = "{uid}"' in pyproject_content
    assert expected_dependency in pyproject_content


@pytest.mark.parametrize(
    ("package_manager", "expected_python_floor"),
    [
        ("uv", 'requires-python = ">=3.13,<4.0"'),
        ("poetry", 'python = ">=3.13,<4.0"'),
    ],
)
def test_copy_template_raises_python_floor_for_uuidv7(
    tmp_path, package_manager, expected_python_floor
):
    destination = tmp_path / f"{package_manager}-uuidv7"

    create_filesystem.copy_template(
        destination,
        "sqlalchemy",
        "ddd",
        "uid-project",
        package_manager,
        "uuidv7",
    )

    pyproject_content = (destination / "pyproject.toml").read_text()

    assert 'uid = "uuidv7"' in pyproject_content
    assert expected_python_floor in pyproject_content


# --- Tests for src/add/utils.py ---

@pytest.mark.parametrize("input_name, expected_lower, expected_cap", [
    ("product", "product", "Product"),
    ("user_profile", "user_profile", "UserProfile"),
    ("My-Service", "my_service", "MyService"),
    ("api response", "api_response", "ApiResponse"),
])
def test_normalize_entity_name(input_name, expected_lower, expected_cap):
    lower, cap = add_utils._normalize_entity_name(input_name)
    assert lower == expected_lower
    assert cap == expected_cap


def test_format_comment():
    assert add_utils._format_comment("") == ""
    assert add_utils._format_comment("  comment") == " # comment"
    assert add_utils._format_comment("# existing") == " # existing"


def test_read_project_config(tmp_path):
    # Missing file
    with pytest.raises(FileNotFoundError):
        add_paths.read_project_config(tmp_path)

    # Missing section
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.other]\nkey='val'")
    with pytest.raises(ValueError, match="No \\[tool.robyn-config\\]"):
        add_paths.read_project_config(tmp_path)

    # Valid config
    pyproject.write_text("[tool.robyn-config]\ndesign='ddd'\norm='sqlalchemy'")
    config = add_paths.read_project_config(tmp_path)
    assert config["design"] == "ddd"
    assert config["orm"] == "sqlalchemy"


def test_ensure_import_from(tmp_path):
    file_path = tmp_path / "test_import.py"

    # 1. New file creation
    add_injection._ensure_import_from(file_path, ".models", "User")
    assert file_path.read_text().strip() == "from .models import User"

    # 2. Append to existing import
    add_injection._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "from .models import User, Product" in content

    # 3. Append with comment preservation
    file_path.write_text("from .models import User  # old comment")
    add_injection._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "from .models import User, Product  # old comment" in content

    # 4. Handle multiline parenthesis import
    file_path.write_text("from .models import (\n    User,\n)")
    add_injection._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "    User," in content
    assert "    Product," in content


def test_add_to_all_list(tmp_path):
    file_path = tmp_path / "test_all.py"

    # Create file with existing __all__
    file_path.write_text('__all__ = (\n    "User",\n)')

    add_injection._add_to_all_list(file_path, "Product")

    content = file_path.read_text()
    assert '"User",' in content
    assert '"Product",' in content
    assert content.count("__all__") == 1


@pytest.mark.parametrize(
    ("design", "uid_line", "expected_uid"),
    [
        ("ddd", "uid = 'sparkid'\n", "sparkid"),
        ("mvc", "", "none"),
    ],
)
def test_add_business_logic_passes_uid_to_template_helpers(
    monkeypatch, tmp_path, design, uid_line, expected_uid
):
    config_lines = [
        "[tool.robyn-config]",
        f"design = '{design}'",
        "orm = 'sqlalchemy'",
    ]
    if uid_line:
        config_lines.append(uid_line.strip())
    (tmp_path / "pyproject.toml").write_text("\n".join(config_lines) + "\n")

    fake_paths = object()
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        add_utils, "_load_add_paths", lambda *_args, **_kwargs: fake_paths
    )
    monkeypatch.setattr(
        add_utils, "_normalize_entity_name", lambda _name: ("product", "Product")
    )

    def fake_add_templates(
        _project_path,
        _paths,
        _name,
        _name_capitalized,
        _orm,
        uid,
    ):
        captured["uid"] = uid
        return ["created.py"]

    if design == "ddd":
        monkeypatch.setattr(add_utils, "_add_ddd_templates", fake_add_templates)
    else:
        monkeypatch.setattr(add_utils, "_add_mvc_templates", fake_add_templates)

    created_files = add_utils.add_business_logic(tmp_path, "product")

    assert created_files == ["created.py"]
    assert captured["uid"] == expected_uid
