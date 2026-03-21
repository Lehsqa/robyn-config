from __future__ import annotations

import io
import logging
import os
import uuid
from typing import Any

import pandas as pd
from robyn import Request, jsonify

from ..helpers import ALLOWED_UPLOAD_EXTENSIONS

logger = logging.getLogger(__name__)


def register_io_routes(site: Any) -> None:
    @site.app.post(f"/{site.prefix}/upload", openapi_name="Admin File Upload", openapi_tags=["Admin"])
    async def file_upload(request: Request):
        try:
            user = await site._get_current_user(request)
            if not user:
                return jsonify(
                    {
                        "code": 401,
                        "message": "Not logged in",
                        "success": False,
                    }
                )

            files = request.files
            if not files:
                return jsonify(
                    {
                        "code": 400,
                        "message": "No file uploaded",
                        "success": False,
                    }
                )

            upload_path = request.form_data.get(
                "upload_path", "static/uploads"
            )
            uploaded_files = []
            for file_name, file_bytes in files.items():
                if not file_name.lower().endswith(ALLOWED_UPLOAD_EXTENSIONS):
                    return jsonify(
                        {
                            "code": 400,
                            "message": "Unsupported file type",
                            "success": False,
                        }
                    )

                safe_filename = (
                    f"{uuid.uuid4().hex}{os.path.splitext(file_name)[1]}"
                )
                os.makedirs(upload_path, exist_ok=True)
                file_path = os.path.join(upload_path, safe_filename)
                with open(file_path, "wb") as file_obj:
                    file_obj.write(file_bytes)

                uploaded_files.append(
                    {
                        "original_name": file_name,
                        "saved_name": safe_filename,
                        "url": f"/{file_path.replace(os.sep, '/')}",
                    }
                )

            return jsonify(
                {
                    "code": 200,
                    "message": "Upload successful",
                    "success": True,
                    "data": uploaded_files[0] if uploaded_files else None,
                }
            )
        except Exception as exc:
            logger.exception("Upload failed")
            return jsonify(
                {
                    "code": 500,
                    "message": f"Upload failed: {exc}",
                    "success": False,
                }
            )

    @site.app.post(f"/{site.prefix}/:route_id/import", openapi_name="Admin Import", openapi_tags=["Admin"])
    async def handle_import(request: Request):
        try:
            user = await site._get_current_user(request)
            if not user:
                return jsonify({"success": False, "message": "Not logged in"})

            route_id = request.path_params.get("route_id")
            if not await site.check_permission(request, route_id, "import"):
                return jsonify(
                    {"success": False, "message": "No import permission"}
                )

            model_admin = site.get_model_admin(route_id)
            if not model_admin or not model_admin.allow_import:
                return jsonify(
                    {
                        "success": False,
                        "message": "Import is not supported",
                    }
                )

            files = request.files
            if not files:
                return jsonify(
                    {"success": False, "message": "No file uploaded"}
                )

            filename = list(files.keys())[0]
            file_data = next(iter(files.values()))
            if not any(
                filename.endswith(ext) for ext in [".xlsx", ".xls", ".csv"]
            ):
                return jsonify(
                    {
                        "success": False,
                        "message": "Only Excel or CSV files are supported",
                    }
                )

            if filename.endswith(".csv"):
                dataframe = pd.read_csv(io.BytesIO(file_data))
            else:
                dataframe = pd.read_excel(io.BytesIO(file_data))

            missing_fields = [
                field
                for field in model_admin.import_fields
                if field not in dataframe.columns
            ]
            if missing_fields:
                return jsonify(
                    {
                        "success": False,
                        "message": (
                            "Missing required fields: "
                            f"{', '.join(missing_fields)}"
                        ),
                    }
                )

            rows = [
                {field: row[field] for field in model_admin.import_fields}
                for _, row in dataframe.iterrows()
            ]
            success_count, error_count, errors = await model_admin.bulk_import(
                rows
            )

            site._record_action(
                username=user.username,
                action="import",
                target=route_id,
                details=f"success={success_count},failed={error_count}",
            )
            return jsonify(
                {
                    "success": True,
                    "message": (
                        "Import completed: "
                        f"{success_count} succeeded, {error_count} failed"
                    ),
                    "errors": errors if errors else None,
                }
            )
        except Exception as exc:
            logger.exception("Import failed")
            return jsonify(
                {"success": False, "message": f"Import failed: {exc}"}
            )
