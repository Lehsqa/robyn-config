from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from robyn import Request, Response, jsonify

from ..context import build_base_context
from ..helpers import first_value


def register_model_view_routes(site: Any) -> None:
    @site.app.get(f"/{site.prefix}/:route_id/search", openapi_name="Admin Model Search", openapi_tags=["Admin"])
    async def model_search(request: Request):
        route_id: str = request.path_params.get("route_id")
        user = await site._get_current_user(request)
        if not user:
            return Response(status_code=401, description="Not logged in")

        model_admin = site.models.get(route_id)
        if not model_admin:
            return Response(status_code=404, description="Model not found")

        search_values = {
            field.name: unquote(
                first_value(
                    request.query_params.get(f"search_{field.name}"), ""
                )
            )
            for field in model_admin.search_fields
            if request.query_params.get(f"search_{field.name}")
        }
        queryset = await model_admin.get_queryset(request, search_values)
        objects = await queryset.limit(model_admin.per_page)

        data = []
        for obj in objects:
            display = await model_admin.serialize_object(obj, for_display=True)
            raw = await model_admin.serialize_object(obj, for_display=False)
            data.append({"display": display, "data": raw})
        return jsonify({"data": data})

    @site.app.get(f"/{site.prefix}/:route_id", openapi_name="Admin Model List", openapi_tags=["Admin"])
    async def model_list(request: Request):
        route_id: str = request.path_params.get("route_id")
        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=303,
                headers={"Location": f"/{site.prefix}/login"},
                description="Not logged in",
            )

        if route_id == "users":
            return Response(
                status_code=303,
                headers={"Location": f"/{site.prefix}/models"},
                description="Users tab moved to models",
            )

        language = await site._get_language(request)
        if not await site.check_permission(request, route_id, "view"):
            return Response(status_code=403, description="Permission denied")

        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return Response(status_code=404, description="model not found")

        frontend_config = await model_admin.get_frontend_config()
        frontend_config["language"] = language
        frontend_config["default_language"] = site.default_language

        context = await build_base_context(
            site,
            request,
            user=user,
            language=language,
            active_tab="models",
        )
        context.update(
            {
                "current_model": route_id,
                "verbose_name": site._get_model_display_name(model_admin),
                "frontend_config": frontend_config,
            }
        )
        return site.jinja_template.render_template(
            "admin/model_list.html", **context
        )

    @site.app.get(f"/{site.prefix}/:route_id/add", openapi_name="Admin Add Model Form", openapi_tags=["Admin"])
    async def model_add(request: Request):
        route_id: str = request.path_params.get("route_id")
        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=303,
                headers={"Location": f"/{site.prefix}/login"},
                description="Not logged in",
            )

        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return Response(status_code=404, description="model not found")

        if not await site.check_permission(request, route_id, "add"):
            return Response(
                status_code=403, description="No create permission"
            )

        language = await site._get_language(request)
        form_fields = [
            field.to_dict() for field in await model_admin.get_form_fields()
        ]
        can_add = model_admin.allow_add and await site.check_permission(
            request, route_id, "add"
        )

        context = await build_base_context(
            site,
            request,
            user=user,
            language=language,
            active_tab="models",
        )
        context.update(
            {
                "current_model": route_id,
                "verbose_name": site._get_model_display_name(model_admin),
                "route_id": route_id,
                "object_id": "",
                "form_fields": form_fields,
                "form_data": {},
                "can_edit": can_add,
                "can_delete": False,
                "is_add_mode": True,
            }
        )
        return site.jinja_template.render_template(
            "admin/model_change.html", **context
        )

    @site.app.get(f"/{site.prefix}/:route_id/:id/change", openapi_name="Admin Change Model Form", openapi_tags=["Admin"])
    async def model_change(request: Request):
        route_id: str = request.path_params.get("route_id")
        object_id: str = unquote(str(request.path_params.get("id", "")))

        user = await site._get_current_user(request)
        if not user:
            return Response(
                status_code=303,
                headers={"Location": f"/{site.prefix}/login"},
                description="Not logged in",
            )

        if not await site.check_permission(request, route_id, "view"):
            return Response(status_code=403, description="Permission denied")

        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return Response(status_code=404, description="model not found")

        obj = await model_admin.get_object(object_id)
        if not obj:
            return Response(status_code=404, description="Record not found")

        language = await site._get_language(request)
        form_fields = [
            field.to_dict() for field in await model_admin.get_form_fields()
        ]
        form_data = await model_admin.serialize_object(obj, for_display=False)
        can_edit = model_admin.enable_edit and await site.check_permission(
            request, route_id, "edit"
        )
        can_delete = model_admin.allow_delete and await site.check_permission(
            request, route_id, "delete"
        )

        context = await build_base_context(
            site,
            request,
            user=user,
            language=language,
            active_tab="models",
        )
        context.update(
            {
                "current_model": route_id,
                "verbose_name": site._get_model_display_name(model_admin),
                "route_id": route_id,
                "object_id": object_id,
                "form_fields": form_fields,
                "form_data": form_data,
                "can_edit": can_edit,
                "can_delete": can_delete,
                "is_add_mode": False,
            }
        )
        return site.jinja_template.render_template(
            "admin/model_change.html", **context
        )
