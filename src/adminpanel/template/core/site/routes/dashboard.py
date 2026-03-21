from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from robyn import Request, Response

from ..context import build_base_context
from ..helpers import body_to_text, first_value


def register_dashboard_routes(site: Any) -> None:
    @site.app.get(f"/{site.prefix}", openapi_name="Admin Dashboard", openapi_tags=["Admin"])
    async def admin_index(request: Request):
        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=307,
                description="Location login page",
                headers={"Location": f"/{site.prefix}/login"},
            )

        language = await site._get_language(request)
        context = await build_base_context(
            site,
            request,
            user=user,
            language=language,
            active_tab="dashboard",
        )
        settings = context["admin_settings"]
        log_lines, resolved_log_path = site._read_log_lines(
            str(settings["log_file_path"]),
            int(settings["log_tail_lines"]),
        )
        context.update(
            {
                "recent_actions": list(reversed(site.recent_actions[-20:])),
                "log_lines": log_lines,
                "resolved_log_path": resolved_log_path,
            }
        )
        return site.jinja_template.render_template(
            "admin/index.html", **context
        )

    @site.app.get(f"/{site.prefix}/models", openapi_name="Admin Models Index", openapi_tags=["Admin"])
    async def models_index(request: Request):
        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=307,
                description="Location login page",
                headers={"Location": f"/{site.prefix}/login"},
            )

        language = await site._get_language(request)
        context = await build_base_context(
            site,
            request,
            user=user,
            language=language,
            active_tab="models",
        )
        return site.jinja_template.render_template(
            "admin/models.html", **context
        )

    @site.app.get(f"/{site.prefix}/users", openapi_name="Admin Users Alias", openapi_tags=["Admin"])
    async def users_alias(request: Request):
        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=307,
                description="Location login page",
                headers={"Location": f"/{site.prefix}/login"},
            )
        return Response(
            status_code=303,
            description="Users tab moved to models",
            headers={"Location": f"/{site.prefix}/models"},
        )

    @site.app.get(f"/{site.prefix}/settings", openapi_name="Admin Settings", openapi_tags=["Admin"])
    async def settings_page(request: Request):
        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=307,
                description="Location login page",
                headers={"Location": f"/{site.prefix}/login"},
            )

        language = await site._get_language(request)
        context = await build_base_context(
            site,
            request,
            user=user,
            language=language,
            active_tab="settings",
        )
        return site.jinja_template.render_template(
            "admin/settings.html", **context
        )

    @site.app.post(f"/{site.prefix}/settings", openapi_name="Save Admin Settings", openapi_tags=["Admin"])
    async def settings_save(request: Request):
        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=307,
                description="Location login page",
                headers={"Location": f"/{site.prefix}/login"},
            )

        current_settings = site._get_admin_settings(request)
        params = parse_qs(body_to_text(request.body))

        log_file_path = first_value(
            params.get("log_file_path"),
            current_settings["log_file_path"],
        )
        if not isinstance(log_file_path, str) or not log_file_path.strip():
            log_file_path = str(current_settings["log_file_path"])

        raw_log_tail = first_value(
            params.get("log_tail_lines"),
            current_settings["log_tail_lines"],
        )
        try:
            log_tail_lines = int(raw_log_tail)
        except Exception:
            log_tail_lines = int(current_settings["log_tail_lines"])
        log_tail_lines = max(20, min(log_tail_lines, 2000))

        theme = first_value(params.get("theme"), current_settings["theme"])
        if theme not in {"dark", "light"}:
            theme = current_settings["theme"]

        updated_settings = {
            "log_file_path": str(log_file_path).strip(),
            "log_tail_lines": log_tail_lines,
            "theme": theme,
        }
        site._record_action(
            username=user.username,
            action="settings_updated",
            target="admin",
            details=f"log_file_path={updated_settings['log_file_path']}",
        )
        return Response(
            status_code=303,
            description="Settings saved",
            headers={
                "Location": f"/{site.prefix}/settings",
                "Set-Cookie": site._build_settings_cookie(updated_settings),
            },
        )
