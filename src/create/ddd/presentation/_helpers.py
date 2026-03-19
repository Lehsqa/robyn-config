"""Helpers for Robyn handlers."""

from robyn import Request


def _normalized_headers(request: Request) -> dict[str, str]:
    raw_headers = getattr(request, "headers", None) or {}
    if isinstance(raw_headers, dict):
        items = raw_headers.items()
    else:
        try:
            items = dict(raw_headers).items()  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - defensive
            try:
                items = raw_headers.items()  # type: ignore[assignment,call-arg]
            except Exception:
                return {}

    headers: dict[str, str] = {}
    for key, value in items:
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(value, bytes):
            value = value.decode()
        headers[str(key).lower()] = str(value)
    return headers


def get_header(request: Request, name: str) -> str | None:
    return _normalized_headers(request).get(name.lower())
