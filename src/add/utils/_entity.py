"""Small helper utilities for the 'add' command."""

from __future__ import annotations


def _normalize_entity_name(name: str) -> tuple[str, str]:
    """Normalize entity name to snake_case and PascalCase variants."""
    normalized = name.lower().replace("-", "_").replace(" ", "_")
    capitalized = "".join(word.capitalize() for word in normalized.split("_"))
    return normalized, capitalized


def _format_comment(comment: str) -> str:
    """Normalize inline comment formatting (adds leading space and #)."""
    if not comment:
        return ""

    cleaned = comment.strip()
    if not cleaned.startswith("#"):
        cleaned = f"# {cleaned}"
    return f" {cleaned}"
