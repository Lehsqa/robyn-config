"""Shared constants for adminpanel scaffolding."""

from __future__ import annotations

from pathlib import Path

ADMINPANEL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = ADMINPANEL_ROOT / "template"

DEFAULT_DDD_DB_TABLE_PATH = Path(
    "src/app/infrastructure/database/tables/__init__.py"
)
LEGACY_DDD_DB_TABLE_PATHS: tuple[Path, ...] = (
    Path("src/app/infrastructure/database/table/__init__.py"),
    Path("src/app/infrastructure/database/tables.py"),
)
DEFAULT_MVC_DB_TABLE_PATH = Path("src/app/models/tables/__init__.py")
LEGACY_MVC_DB_TABLE_PATHS: tuple[Path, ...] = (
    Path("src/app/models/table/__init__.py"),
    Path("src/app/models/models.py"),
)

ADMIN_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("jinja2", ">=3.0.0"),
    ("aiosqlite", ">=0.17.0"),
    ("pandas", ">=1.0.0"),
    ("openpyxl", ">=3.0.0"),
)

SUPPORTED_DESIGNS = ("ddd", "mvc")
SUPPORTED_ORMS = ("tortoise", "sqlalchemy")
SUPPORTED_PACKAGE_MANAGERS = ("poetry", "uv")

DDD_APP_PANEL_TEMPLATE = """\
from __future__ import annotations

from robyn import Robyn

from app.infrastructure import adminpanel as adminpanel_module


def register(app: Robyn) -> None:
    adminpanel_module.register(app)
"""

SQLALCHEMY_ADMIN_TABLES_SNIPPET = """\
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .authentication import UsersTable
from .base import Base


class Role(Base):
    __tablename__ = "robyn_admin_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accessible_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )


class UserRole(Base):
    __tablename__ = "robyn_admin_user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[object] = mapped_column(
        UsersTable.__table__.c.id.type.copy(),
        ForeignKey(f"{UsersTable.__tablename__}.id", ondelete="CASCADE"),
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("robyn_admin_roles.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )
"""

TORTOISE_ADMIN_TABLES_SNIPPET = """\
from __future__ import annotations

from tortoise import fields

from .base import BaseTable


class Role(BaseTable):
    name = fields.CharField(max_length=150, unique=True)
    description = fields.CharField(max_length=200, null=True)
    accessible_models = fields.JSONField(default=list)

    class Meta:
        table = "robyn_admin_roles"
        ordering = ("id",)


class UserRole(BaseTable):
    user = fields.ForeignKeyField("models.UsersTable", related_name="user_roles")
    role = fields.ForeignKeyField("models.Role", related_name="role_users")

    class Meta:
        table = "robyn_admin_user_roles"
        ordering = ("id",)
"""

SQLALCHEMY_ADMIN_TABLES_LEGACY_SNIPPET = """\
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column


class Role(Base):
    __tablename__ = "robyn_admin_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accessible_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )


class UserRole(Base):
    __tablename__ = "robyn_admin_user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[object] = mapped_column(
        UsersTable.__table__.c.id.type.copy(),
        ForeignKey(f"{UsersTable.__tablename__}.id", ondelete="CASCADE"),
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("robyn_admin_roles.id", ondelete="CASCADE"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.CURRENT_TIMESTAMP(),
    )
"""

TORTOISE_ADMIN_TABLES_LEGACY_SNIPPET = """\
from __future__ import annotations

from tortoise import fields


class Role(BaseTable):
    name = fields.CharField(max_length=150, unique=True)
    description = fields.CharField(max_length=200, null=True)
    accessible_models = fields.JSONField(default=list)

    class Meta:
        table = "robyn_admin_roles"
        ordering = ("id",)


class UserRole(BaseTable):
    user = fields.ForeignKeyField("models.UsersTable", related_name="user_roles")
    role = fields.ForeignKeyField("models.Role", related_name="role_users")

    class Meta:
        table = "robyn_admin_user_roles"
        ordering = ("id",)
"""
