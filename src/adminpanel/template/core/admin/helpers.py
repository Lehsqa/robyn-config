from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import Integer
from sqlalchemy.inspection import inspect as sa_inspect


def _get_model_column(model: type[Any], name: str):
    mapper = sa_inspect(model)
    for column in mapper.columns:
        if column.name == name:
            return getattr(model, column.name)
    return None


def _coerce_pk(value: Any, column: Any | None) -> Any:
    if column is None:
        return value
    try:
        if isinstance(column.type, Integer):
            return int(value)
    except Exception:
        return value
    return value


def _normalize_filter_value(value: Any) -> Any:
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def _normalize_in_lookup_value(value: Any) -> list[Any]:
    if isinstance(value, str):
        return [item for item in value.split(",") if item]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _build_filter_expression(model: type[Any], key: str, value: Any):
    if "__" in key:
        name, operator_name = key.split("__", 1)
    else:
        name, operator_name = key, "exact"

    column = _get_model_column(model, name)
    if column is None:
        return None

    normalized_value = _normalize_filter_value(value)
    operator_map: dict[str, Callable[[Any], Any]] = {
        "exact": lambda current_value: column == current_value,
        "icontains": lambda current_value: column.ilike(
            f"%{current_value}%"
        ),
        "contains": lambda current_value: column.contains(current_value),
        "in": lambda current_value: column.in_(
            _normalize_in_lookup_value(current_value)
        ),
        "gte": lambda current_value: column >= current_value,
        "lte": lambda current_value: column <= current_value,
        "gt": lambda current_value: column > current_value,
        "lt": lambda current_value: column < current_value,
    }
    operator_fn = operator_map.get(operator_name)
    if operator_fn is None:
        return None
    return operator_fn(normalized_value)


def _is_boolean_column(column: Any) -> bool:
    try:
        return column.type.python_type is bool
    except Exception:
        return False
