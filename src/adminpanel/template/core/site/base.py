from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminSettingsConfig(BaseModel):
    """Validated admin settings payload stored in cookie."""

    log_file_path: str = "logs/app.log"
    log_tail_lines: int = 200
    theme: str = "dark"

    @field_validator("log_file_path", mode="before")
    @classmethod
    def _normalize_log_file_path(cls, value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "logs/app.log"

    @field_validator("log_tail_lines", mode="before")
    @classmethod
    def _normalize_log_tail_lines(cls, value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 200
        return max(20, min(parsed, 2000))

    @field_validator("theme", mode="before")
    @classmethod
    def _normalize_theme(cls, value: Any) -> str:
        if value in {"dark", "light"}:
            return str(value)
        return "dark"


class SiteRuntimeConfig(BaseModel):
    """Typed configuration for AdminSite initialization."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: str = "QC Robyn Admin"
    prefix: str = "admin"
    copyright: str = "QC Robyn Admin"
    default_language: str = "en_US"
    default_admin_username: str = "admin"
    default_admin_password: str = "admin"
    startup_function: Callable[..., Any] | None = None
    generate_schemas: bool = False
    orm: str = ""
    max_recent_actions: int = 100
    default_settings: AdminSettingsConfig = Field(
        default_factory=AdminSettingsConfig
    )


_MODEL_ATTR_PATHS: dict[str, tuple[tuple[str, ...], ...]] = {
    "table_name": (("__tablename__",), ("_meta", "db_table")),
    "module_name": (("__module__",),),
}


def _read_attr_by_path(source: Any, path: tuple[str, ...]) -> Any:
    current = source
    for part in path:
        if current is None:
            return None
        current = getattr(current, part, None)
    return current


def _resolve_string_attribute(
    source: Any, paths: tuple[tuple[str, ...], ...]
) -> str:
    for path in paths:
        value = _read_attr_by_path(source, path)
        if isinstance(value, str) and value:
            return value
    return ""


class ModelAdminMetadata(BaseModel):
    """Normalized metadata extracted from model admin registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    table_name: str = ""
    module_name: str = ""
    verbose_name: str = "Model"

    @classmethod
    def from_model_admin(cls, model_admin: Any) -> "ModelAdminMetadata":
        model = getattr(model_admin, "model", None)
        values: dict[str, Any] = {}
        for field_name, attr_paths in _MODEL_ATTR_PATHS.items():
            values[field_name] = _resolve_string_attribute(model, attr_paths)
        values["verbose_name"] = str(
            getattr(model_admin, "verbose_name", "Model")
        )
        return cls.model_validate(values)


_PLURALIZATION_RULES: dict[
    str, tuple[Callable[[str], bool], Callable[[str], str]]
] = {
    "already_plural": (
        lambda lower_word: lower_word.endswith("s"),
        lambda word: word,
    ),
    "es_suffix": (
        lambda lower_word: lower_word.endswith(("x", "z", "ch", "sh")),
        lambda word: f"{word}es",
    ),
    "ies_suffix": (
        lambda lower_word: (
            lower_word.endswith("y")
            and len(lower_word) > 1
            and lower_word[-2] not in {"a", "e", "i", "o", "u"}
        ),
        lambda word: f"{word[:-1]}ies",
    ),
}


def pluralize_word(word: str) -> str:
    lower_word = word.lower()
    for predicate, transform in _PLURALIZATION_RULES.values():
        if predicate(lower_word):
            return transform(word)
    return f"{word}s"


def merge_admin_settings(
    *,
    cookie_header: str | None,
    default_settings: dict[str, Any],
    parse_cookie_header: Callable[[str], dict[str, str]],
    decode_cookie_payload: Callable[[str], str],
) -> dict[str, Any]:
    merged = dict(default_settings)
    if not cookie_header:
        return merged

    cookies = parse_cookie_header(cookie_header)
    raw_payload = cookies.get("admin_settings")
    if not raw_payload:
        return merged

    try:
        decoded_payload = decode_cookie_payload(raw_payload)
        decoded_settings = json.loads(decoded_payload)
    except Exception:
        return merged

    if not isinstance(decoded_settings, dict):
        return merged

    try:
        validated = AdminSettingsConfig.model_validate(
            {**merged, **decoded_settings}
        )
    except Exception:
        return merged

    return validated.model_dump()
