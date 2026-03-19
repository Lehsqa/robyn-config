from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from robyn import Request, Response, jsonify

from ..helpers import body_to_text, first_value, parse_form_payload, to_int


def register_model_mutation_routes(site: Any) -> None:
    @site.app.post(f"/{site.prefix}/:route_id/add")
    async def model_add_post(request: Request):
        route_id: str = request.path_params.get("route_id")
        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return Response(status_code=404, description="Model not found")
        if not await site.check_permission(request, route_id, "add"):
            return Response(
                status_code=403, description="No create permission"
            )

        params = parse_qs(body_to_text(request.body))
        form_data = parse_form_payload(params)
        success, message = await model_admin.handle_add(request, form_data)
        if success:
            user = await site._get_current_user(request)
            if user:
                site._record_action(
                    username=user.username,
                    action="create",
                    target=route_id,
                )
        return Response(
            status_code=200 if success else 400,
            description=message,
            headers={"Content-Type": "text/html"},
        )

    @site.app.post(f"/{site.prefix}/:route_id/:id/edit")
    async def model_edit_post(request: Request):
        route_id: str = request.path_params.get("route_id")
        object_id: str = request.path_params.get("id")

        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return Response(status_code=404, description="Model not found")
        if not model_admin.enable_edit:
            return Response(
                status_code=403, description="model not allow edit"
            )
        if not await site.check_permission(request, route_id, "edit"):
            return Response(status_code=403, description="No edit permission")

        params = parse_qs(body_to_text(request.body))
        form_data = parse_form_payload(params)
        success, message = await model_admin.handle_edit(
            request,
            object_id,
            form_data,
        )
        if success:
            user = await site._get_current_user(request)
            if user:
                site._record_action(
                    username=user.username,
                    action="update",
                    target=f"{route_id}:{object_id}",
                )
        return Response(
            status_code=200 if success else 400,
            description=message,
            headers={"Content-Type": "text/html"},
        )

    @site.app.post(f"/{site.prefix}/:route_id/:id/delete")
    async def model_delete(request: Request):
        route_id: str = request.path_params.get("route_id")
        object_id: str = request.path_params.get("id")
        user = await site._get_current_user(request)
        if not user:
            return Response(status_code=401, description="Not logged in")

        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return Response(status_code=404, description="Model not found")
        if not await site.check_permission(request, route_id, "delete"):
            return Response(
                status_code=403, description="No delete permission"
            )

        success, message = await model_admin.handle_delete(request, object_id)
        if success:
            site._record_action(
                username=user.username,
                action="delete",
                target=f"{route_id}:{object_id}",
            )
        return Response(
            status_code=200 if success else 400,
            description=message,
            headers={"Content-Type": "text/html"},
        )

    @site.app.get(f"/{site.prefix}/:route_id/data")
    async def model_data(request: Request):
        route_id: str = request.path_params.get("route_id")
        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return jsonify({"error": "Model not found"})

        params: dict = request.query_params.to_dict()
        query_params = {
            "limit": max(1, to_int(first_value(params.get("limit"), 10), 10)),
            "offset": max(0, to_int(first_value(params.get("offset"), 0), 0)),
            "search": first_value(params.get("search"), ""),
            "sort": first_value(params.get("sort"), ""),
            "order": first_value(params.get("order"), "asc"),
        }
        for key, value in params.items():
            if key not in {"limit", "offset", "search", "sort", "order", "_"}:
                query_params[key] = first_value(value)

        queryset, total = await model_admin.handle_query(request, query_params)
        data = []
        async for obj in queryset:
            serialized = await model_admin.serialize_object(obj)
            data.append({"data": serialized, "display": serialized})

        return jsonify({"total": total, "data": data})

    @site.app.post(f"/{site.prefix}/:route_id/batch_delete")
    async def model_batch_delete(request: Request):
        route_id: str = request.path_params.get("route_id")
        user = await site._get_current_user(request)
        if not user:
            return Response(status_code=401, description="Not logged in")

        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return Response(status_code=404, description="Model not found")

        params = parse_qs(body_to_text(request.body))
        ids = params.get("ids[]", [])
        if not ids:
            return jsonify(
                {
                    "code": 400,
                    "message": "No records selected",
                    "success": False,
                }
            )

        success, message, deleted_count = (
            await model_admin.handle_batch_delete(
                request,
                ids,
            )
        )
        if success:
            site._record_action(
                username=user.username,
                action="batch_delete",
                target=route_id,
                details=f"deleted_count={deleted_count}",
            )
        return jsonify(
            {
                "code": 200 if success else 500,
                "message": message,
                "success": success,
                "data": {"deleted_count": deleted_count},
            }
        )

    @site.app.get(f"/{site.prefix}/:route_id/inline_data")
    async def get_inline_data(request: Request):
        route_id = request.path_params.get("route_id")
        model_admin = site.get_model_admin(route_id)
        if not model_admin:
            return jsonify({"error": "Model not found"})

        params: dict = request.query_params.to_dict()
        parent_id = first_value(params.get("parent_id"), "")
        inline_model = first_value(params.get("inline_model"), "")
        if not parent_id or not inline_model:
            return jsonify({"error": "Missing parameters"})

        data = await model_admin.get_inline_data(parent_id, inline_model)
        return jsonify(
            {
                "success": True,
                "data": data,
                "total": len(data),
                "fields": [],
            }
        )
