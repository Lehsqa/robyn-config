from __future__ import annotations

from typing import Any

from robyn import Request


async def build_base_context(
    site: Any,
    request: Request,
    *,
    user: Any,
    language: str,
    active_tab: str,
) -> dict[str, Any]:
    settings = site._get_admin_settings(request)
    visible_models = await site._get_visible_models(request)
    model_categories = site._build_model_categories(visible_models)
    return {
        "site_title": site.title,
        "models": visible_models,
        "model_categories": model_categories,
        "user": user,
        "language": language,
        "copyright": site.copyright,
        "active_tab": active_tab,
        "admin_settings": settings,
    }
