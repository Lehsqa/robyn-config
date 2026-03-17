from __future__ import annotations

import asyncio
from typing import Any


def _coerce_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off", ""}:
            return False

    return bool(value)


async def _await_if_needed(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    if hasattr(value, "__await__"):
        return await value
    return value


def _normalize_collection(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        return list(value)
    except TypeError:
        return [value]


def _resolve_related_field_name(
    field_name: str, related_model: type[Any]
) -> str:
    model_prefix = f"{related_model.__name__}_"
    if field_name.startswith(model_prefix):
        resolved = field_name[len(model_prefix) :]
        if resolved:
            return resolved
    parts = field_name.split("_")
    if len(parts) > 1:
        return parts[-1]
    return "id"


async def _query_related_objects(
    related_model: type[Any], lookup: str, value: str
) -> list[Any]:
    filter_method = getattr(related_model, "filter", None)
    if not callable(filter_method):
        return []

    try:
        result = filter_method(**{lookup: value})
        resolved = await _await_if_needed(result)
    except Exception:
        return []

    return _normalize_collection(resolved)


def _extract_related_ids(objects: list[Any]) -> list[Any]:
    related_ids: list[Any] = []
    for obj in objects:
        obj_id = getattr(obj, "id", None)
        if obj_id is not None:
            related_ids.append(obj_id)
    return related_ids
