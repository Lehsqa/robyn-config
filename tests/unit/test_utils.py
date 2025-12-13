import pytest
from pathlib import Path
from unittest.mock import patch

from src.create import utils as create_utils
from src.add import utils as add_utils


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

    with patch("src.create.utils.COMMON_DIR", common_dir):
        # SQLAlchemy should include everything (alembic.ini is kept)
        items_sql = create_utils._collect_common_items("sqlalchemy", "uv")
        assert Path("Makefile") in items_sql
        assert Path("README.md") in items_sql
        assert Path("alembic.ini") in items_sql
        assert Path("uv.lock") in items_sql
        assert Path("poetry.lock") not in items_sql
        assert Path("compose") not in items_sql
        assert Path(".DS_Store") not in items_sql

        # Tortoise should exclude alembic.ini
        items_tortoise = create_utils._collect_common_items(
            "tortoise", "poetry"
        )
        assert Path("Makefile") in items_tortoise
        assert Path("README.md") in items_tortoise
        assert Path("alembic.ini") not in items_tortoise
        assert Path("poetry.lock") in items_tortoise
        assert Path("uv.lock") not in items_tortoise


def test_get_template_config():
    """Test that template config is retrieved correctly."""
    config = create_utils._get_template_config(
        "ddd", "sqlalchemy", "mypro", "uv"
    )
    assert config["design"] == "ddd"
    assert config["orm"] == "sqlalchemy"
    assert config["name"] == "mypro"
    assert config["package_manager"] == "uv"

    with pytest.raises(SystemExit):
        create_utils._get_template_config("invalid", "orm", "proj", "uv")


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
        add_utils.read_project_config(tmp_path)

    # Missing section
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.other]\nkey='val'")
    with pytest.raises(ValueError, match="No \\[tool.robyn-config\\]"):
        add_utils.read_project_config(tmp_path)

    # Valid config
    pyproject.write_text("[tool.robyn-config]\ndesign='ddd'\norm='sqlalchemy'")
    config = add_utils.read_project_config(tmp_path)
    assert config["design"] == "ddd"
    assert config["orm"] == "sqlalchemy"


def test_ensure_import_from(tmp_path):
    file_path = tmp_path / "test_import.py"
    
    # 1. New file creation
    add_utils._ensure_import_from(file_path, ".models", "User")
    assert file_path.read_text().strip() == "from .models import User"

    # 2. Append to existing import
    add_utils._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "from .models import User, Product" in content

    # 3. Append with comment preservation
    file_path.write_text("from .models import User  # old comment")
    add_utils._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "from .models import User, Product  # old comment" in content

    # 4. Handle multiline parenthesis import
    file_path.write_text("from .models import (\n    User,\n)")
    add_utils._ensure_import_from(file_path, ".models", "Product")
    content = file_path.read_text()
    assert "    User," in content
    assert "    Product," in content


def test_add_to_all_list(tmp_path):
    file_path = tmp_path / "test_all.py"
    
    # Create file with existing __all__
    file_path.write_text('__all__ = (\n    "User",\n)')
    
    add_utils._add_to_all_list(file_path, "Product")
    
    content = file_path.read_text()
    assert '"User",' in content
    assert '"Product",' in content
    assert content.count("__all__") == 1
