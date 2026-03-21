from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs

from robyn import Request, Response

from ..helpers import body_to_text, first_value

logger = logging.getLogger(__name__)

AuthenticateUser = Callable[[Any, str, str], Awaitable[tuple[int, str] | None]]


def register_auth_routes(
    site: Any, *, authenticate_user: AuthenticateUser
) -> None:
    @site.app.get(f"/{site.prefix}/login", openapi_name="Admin Login Page", openapi_tags=["Admin"])
    async def admin_login(request: Request):
        user = await site._get_current_user(request)
        if user:
            return Response(
                status_code=307,
                description="Location to admin page",
                headers={"Location": f"/{site.prefix}"},
            )

        language = await site._get_language(request)
        context = {
            "user": None,
            "language": language,
            "site_title": site.title,
            "copyright": site.copyright,
            "active_tab": "",
            "admin_settings": site._get_admin_settings(request),
        }
        return site.jinja_template.render_template(
            "admin/login.html", **context
        )

    @site.app.post(f"/{site.prefix}/login", openapi_name="Admin Login", openapi_tags=["Admin"])
    async def admin_login_post(request: Request):
        try:
            params = parse_qs(body_to_text(request.body))
            username = first_value(params.get("username"), "")
            password = first_value(params.get("password"), "")

            auth_result = await authenticate_user(site, username, password)
            if not auth_result:
                language = await site._get_language(request)
                context = {
                    "error": "Invalid username or password",
                    "user": None,
                    "language": language,
                    "site_title": site.title,
                    "copyright": site.copyright,
                    "active_tab": "",
                    "admin_settings": site._get_admin_settings(request),
                }
                return site.jinja_template.render_template(
                    "admin/login.html", **context
                )

            user_id, authenticated_username = auth_result
            site._record_action(
                username=authenticated_username,
                action="login",
                target="admin",
            )

            token = site._generate_session_token(user_id)
            cookie_attrs = [
                f"session_token={token}",
                "HttpOnly",
                "Path=/",
                f"Max-Age={site.session_expire}",
            ]
            return Response(
                status_code=303,
                description="Login successful",
                headers={
                    "Location": f"/{site.prefix}",
                    "Set-Cookie": "; ".join(cookie_attrs),
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                },
            )
        except Exception as exc:
            logger.exception("Login failed")
            return Response(
                status_code=500, description=f"Login failed: {exc}"
            )

    @site.app.get(f"/{site.prefix}/logout", openapi_name="Admin Logout", openapi_tags=["Admin"])
    async def admin_logout(request: Request):
        user = await site._get_current_user(request)
        if user:
            site._record_action(
                username=user.username,
                action="logout",
                target="admin",
            )

        return Response(
            status_code=303,
            description="",
            headers={
                "Location": f"/{site.prefix}/login",
                "Set-Cookie": "; ".join(
                    [
                        "session_token=",
                        "HttpOnly",
                        "Path=/",
                        "Max-Age=0",
                    ]
                ),
            },
        )

    @site.app.post(f"/{site.prefix}/set_language", openapi_name="Set Language", openapi_tags=["Admin"])
    async def set_language(request: Request):
        try:
            params = parse_qs(body_to_text(request.body))
            language = first_value(
                params.get("language"), site.default_language
            )
            cookie_attrs = [
                f"session={json.dumps({'language': language})}",
                "HttpOnly",
                "Path=/",
            ]
            return Response(
                status_code=200,
                description="Language set successfully",
                headers={"Set-Cookie": "; ".join(cookie_attrs)},
            )
        except Exception:
            return Response(
                status_code=500,
                description="Set language failed",
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
