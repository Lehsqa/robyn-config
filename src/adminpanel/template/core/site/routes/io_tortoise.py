from __future__ import annotations

import io
import os
import traceback
import uuid
from typing import Any

import pandas as pd
from robyn import Request, jsonify

from ..helpers import ALLOWED_UPLOAD_EXTENSIONS


def register_io_routes(site: Any) -> None:
    @site.app.post(f"/{site.prefix}/upload")
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

            upload_path = request.form_data.get("upload_path", "static/uploads")
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

                safe_filename = f"{uuid.uuid4().hex}{os.path.splitext(file_name)[1]}"
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
            traceback.print_exc()
            return jsonify(
                {
                    "code": 500,
                    "message": f"Upload failed: {exc}",
                    "success": False,
                }
            )

    @site.app.post(f"/{site.prefix}/:route_id/import")
    async def handle_import(request: Request):
        try:
            route_id = request.path_params.get("route_id")
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
                return jsonify({"success": False, "message": "No file uploaded"})

            filename = list(files.keys())[0]
            file_data = next(iter(files.values()))
            if not any(filename.endswith(ext) for ext in [".xlsx", ".xls", ".csv"]):
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

            success_count = 0
            error_count = 0
            errors: list[str] = []
            for _, row in dataframe.iterrows():
                try:
                    payload = {
                        field: row[field] for field in model_admin.import_fields
                    }
                    await model_admin.model.create(**payload)
                    success_count += 1
                except Exception as exc:
                    error_count += 1
                    errors.append(str(exc))

            user = await site._get_current_user(request)
            if user:
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
            traceback.print_exc()
            return jsonify({"success": False, "message": f"Import failed: {exc}"})
