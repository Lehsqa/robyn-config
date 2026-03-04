import os
import quopri
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
ACTIVATION_PATTERN = re.compile(r"http://[^/]+/activate/([0-9a-fA-F-]+)")
APP_BASE_URL = "http://127.0.0.1:8000"
MAILHOG_API = "http://127.0.0.1:8025/api/v2/messages"

COMBINATIONS = [
    ("ddd", "sqlalchemy"),
    ("ddd", "tortoise"),
    ("mvc", "sqlalchemy"),
    ("mvc", "tortoise"),
]
ADMIN_USER_ROUTE = "AdminUserAdmin"
ROLE_ROUTE = "RoleAdmin"
USER_ROLE_ROUTE = "UserRoleAdmin"


def run_cli_create(destination: Path, design: str, orm: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "create",
            "integration-app",
            "--orm",
            orm,
            "--design",
            design,
            str(destination),
        ],
        check=True,
        env=env,
    )


def run_cli_add(project_path: Path, name: str) -> None:
    """Add business logic to an existing project using the CLI."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "add",
            name,
            str(project_path),
        ],
        check=True,
        env=env,
    )


def run_adminpanel(project_path: Path) -> None:
    """Add adminpanel to an existing project using the CLI."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cli",
            "adminpanel",
            str(project_path),
        ],
        check=True,
        env=env,
    )


def run_make_migration(project_dir: Path, design: str, orm: str) -> None:
    """Run make makemigration in the project directory."""
    try:
        if orm == "sqlalchemy":
            subprocess.run(
                ["make", "migrate"],
                cwd=project_dir,
                check=True,
                capture_output=True,
            )

            subprocess.run(
                ["make", "makemigration"],
                cwd=project_dir,
                check=True,
                capture_output=True,
            )

    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")
        print(f"STDOUT: {e.stdout.decode()}")
        print(f"STDERR: {e.stderr.decode()}")
        raise e


def docker_compose(project_dir: Path, *args: str) -> None:
    env = {**os.environ, "COMPOSE_HTTP_TIMEOUT": "200"}
    subprocess.run(
        ["docker", "compose", *args],
        cwd=project_dir,
        check=True,
        env=env,
    )


def _get_app_container_logs(project_dir: Path, tail: int = 200) -> str:
    env = {**os.environ, "COMPOSE_HTTP_TIMEOUT": "200"}
    result = subprocess.run(
        ["docker", "compose", "logs", "--tail", str(tail), "app"],
        cwd=project_dir,
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    output = result.stdout.strip()
    stderr = result.stderr.strip()
    if stderr:
        output = f"{output}\n{stderr}".strip()
    return output or "<no app logs captured>"


def wait_for_health(project_dir: Path, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{APP_BASE_URL}/health", timeout=timeout)
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1)

    app_logs = _get_app_container_logs(project_dir)
    error_lines = ["App health check did not become available in time"]
    if last_error:
        error_lines.append(f"Last health probe error: {last_error}")
    error_lines += ["App container logs:", app_logs]
    pytest.fail("\n".join(error_lines))


def fetch_activation_key(timeout: float = 120.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = httpx.get(MAILHOG_API, timeout=5.0)
            response.raise_for_status()
        except httpx.HTTPError:
            time.sleep(1)
            continue
        for message in response.json().get("items", []):
            body = message.get("Content", {}).get("Body", "")
            decoded = quopri.decodestring(body.encode()).decode(errors="ignore")
            match = ACTIVATION_PATTERN.search(decoded)
            if match:
                token = match.group(1).strip()
                cleaned = token.lstrip("{").rstrip("}")
                try:
                    normalized = str(uuid.UUID(cleaned))
                except ValueError:
                    continue
                return normalized
        time.sleep(1)
    pytest.fail("Activation email was not delivered")


def clear_mailhog_queue() -> None:
    try:
        httpx.delete(MAILHOG_API, timeout=5.0)
    except httpx.HTTPError:
        pass


def _admin_login(
    client: httpx.Client, username: str, password: str
) -> httpx.Response:
    return client.post(
        "/admin/login",
        content=f"username={username}&password={password}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def _admin_data(client: httpx.Client, route_id: str) -> dict:
    response = client.get(
        f"/admin/{route_id}/data",
        params={"limit": 200, "offset": 0},
    )
    response.raise_for_status()
    payload = response.json()
    assert "total" in payload
    assert "data" in payload
    return payload


def _find_row_by_field(
    rows: list[dict], field_name: str, field_value: str
) -> dict | None:
    expected = str(field_value)
    for row in rows:
        data = row.get("data", {})
        if str(data.get(field_name, "")) == expected:
            return row
    return None


def test_wait_for_health_includes_app_logs_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ticks = iter([0.0, 0.2, 0.4, 5.2])

    monkeypatch.setattr(time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(time, "sleep", lambda _: None)

    def fake_get(url: str, timeout: float) -> None:
        raise httpx.ConnectError(
            "connection refused",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    docker_calls: list[list[str]] = []

    def fake_run(
        args: list[str],
        cwd: Path,
        check: bool,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess:
        docker_calls.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="app log line",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        wait_for_health(tmp_path, timeout=5.0)

    error_message = str(exc_info.value)
    assert "App container logs:" in error_message
    assert "app log line" in error_message
    assert docker_calls == [["docker", "compose", "logs", "--tail", "200", "app"]]


@pytest.mark.integration
@pytest.mark.parametrize("design,orm", COMBINATIONS)
def test_generate_app_and_run_endpoints(
    tmp_path: Path, design: str, orm: str
) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker is required for this integration test")

    project_dir = tmp_path / "robyn-app"
    shutil.rmtree(project_dir, ignore_errors=True)
    run_cli_create(project_dir, design=design, orm=orm)
    run_cli_add(project_dir, "product")
    run_adminpanel(project_dir)
    run_make_migration(project_dir, design, orm)
    shutil.copy2(project_dir / ".env.example", project_dir / ".env")

    compose_started = False
    try:
        docker_compose(project_dir, "up", "-d", "--build")
        compose_started = True
        wait_for_health(project_dir)
        clear_mailhog_queue()

        user_payload = {
            "username": "user",
            "email": "user@email.com",
            "password": "12Qwerty%",
        }
        with httpx.Client(base_url=APP_BASE_URL, timeout=10.0) as client:
            # === Test Admin Panel endpoints (from adminpanel command) ===
            # Test GET /admin (unauthenticated redirect)
            unauth_admin_response = client.get("/admin")
            assert unauth_admin_response.status_code in {
                303,
                307,
            }, f"Unexpected unauthenticated /admin response: {unauth_admin_response.status_code}"
            assert unauth_admin_response.headers.get("Location") == "/admin/login"

            # Test POST /admin/login (invalid credentials)
            invalid_admin_login = _admin_login(
                client, username="admin", password="wrong-password"
            )
            assert (
                invalid_admin_login.status_code == 200
            ), f"Unexpected invalid login status: {invalid_admin_login.status_code}"
            assert "Invalid username or password" in invalid_admin_login.text

            # Test POST /admin/login (valid credentials)
            admin_login_response = _admin_login(
                client, username="admin", password="admin"
            )
            assert (
                admin_login_response.status_code == 303
            ), f"Admin login failed: {admin_login_response.text}"

            # Test GET /admin (index)
            admin_index_response = client.get("/admin")
            assert (
                admin_index_response.status_code == 200
            ), f"Admin index failed: {admin_index_response.text}"

            # Test GET /admin/:route_id (model list)
            admin_model_list_response = client.get(f"/admin/{ADMIN_USER_ROUTE}")
            assert (
                admin_model_list_response.status_code == 200
            ), f"Admin model list failed: {admin_model_list_response.text}"

            # Test POST /admin/set_language
            set_language_response = client.post(
                "/admin/set_language",
                content="language=en_US",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert (
                set_language_response.status_code == 200
            ), f"Set language failed: {set_language_response.text}"

            # Test GET /admin/:route_id/data (admin users data)
            admin_users_payload = _admin_data(client, ADMIN_USER_ROUTE)
            admin_users_total = int(admin_users_payload["total"])
            admin_rows = admin_users_payload["data"]
            assert admin_rows, "Expected admin users data to contain at least one record"
            admin_id = str(admin_rows[0]["data"]["id"])

            # Test GET /admin/:route_id/search
            admin_search_response = client.get(f"/admin/{ADMIN_USER_ROUTE}/search")
            assert (
                admin_search_response.status_code == 200
            ), f"Admin search failed: {admin_search_response.text}"
            search_payload = admin_search_response.json()
            assert "data" in search_payload

            # Test POST /admin/:route_id/:id/edit (boolean fields)
            admin_edit_response = client.post(
                f"/admin/{ADMIN_USER_ROUTE}/{admin_id}/edit",
                content="is_active=on&is_superuser=on",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert (
                admin_edit_response.status_code == 200
            ), f"Admin edit failed: {admin_edit_response.text}"

            run_id = uuid.uuid4().hex[:8]

            # Test POST /admin/:route_id/add (single create)
            single_username = f"admin-single-{run_id}"
            single_email = f"{single_username}@example.com"
            admin_add_single_response = client.post(
                f"/admin/{ADMIN_USER_ROUTE}/add",
                content=(
                    f"username={single_username}&email={single_email}"
                    "&password=admin123&is_active=true&is_superuser=false"
                ),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert (
                admin_add_single_response.status_code == 200
            ), f"Admin add failed: {admin_add_single_response.text}"

            users_after_single_add = _admin_data(client, ADMIN_USER_ROUTE)
            assert int(users_after_single_add["total"]) == admin_users_total + 1
            single_user_row = _find_row_by_field(
                users_after_single_add["data"], "username", single_username
            )
            assert (
                single_user_row is not None
            ), "Newly created admin user not found"
            single_user_id = str(single_user_row["data"]["id"])

            # Test POST /admin/:route_id/:id/edit (single edit)
            single_edit_response = client.post(
                f"/admin/{ADMIN_USER_ROUTE}/{single_user_id}/edit",
                content="is_active=false&is_superuser=false",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert (
                single_edit_response.status_code == 200
            ), f"Single-user edit failed: {single_edit_response.text}"

            # Test POST /admin/:route_id/:id/delete (single delete)
            single_delete_response = client.post(
                f"/admin/{ADMIN_USER_ROUTE}/{single_user_id}/delete"
            )
            assert (
                single_delete_response.status_code == 200
            ), f"Single-user delete failed: {single_delete_response.text}"

            users_after_single_delete = _admin_data(client, ADMIN_USER_ROUTE)
            assert int(users_after_single_delete["total"]) == admin_users_total

            # Test POST /admin/:route_id/add + /batch_delete (bulk users)
            batch_users: list[tuple[str, str]] = []
            for index in range(2):
                username = f"admin-batch-{run_id}-{index}"
                email = f"{username}@example.com"
                batch_users.append((username, email))
                batch_add_response = client.post(
                    f"/admin/{ADMIN_USER_ROUTE}/add",
                    content=(
                        f"username={username}&email={email}"
                        "&password=admin123&is_active=true&is_superuser=false"
                    ),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                )
                assert (
                    batch_add_response.status_code == 200
                ), f"Batch admin add failed: {batch_add_response.text}"

            users_after_batch_add = _admin_data(client, ADMIN_USER_ROUTE)
            assert int(users_after_batch_add["total"]) == admin_users_total + 2
            batch_user_ids: list[str] = []
            for username, _ in batch_users:
                row = _find_row_by_field(
                    users_after_batch_add["data"], "username", username
                )
                assert row is not None, f"Batch admin user {username} not found"
                batch_user_ids.append(str(row["data"]["id"]))

            batch_delete_response = client.post(
                f"/admin/{ADMIN_USER_ROUTE}/batch_delete",
                content=(
                    f"ids%5B%5D={batch_user_ids[0]}&"
                    f"ids%5B%5D={batch_user_ids[1]}"
                ),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert (
                batch_delete_response.status_code == 200
            ), f"Batch delete request failed: {batch_delete_response.text}"
            batch_delete_payload = batch_delete_response.json()
            assert batch_delete_payload["success"] is True
            assert (
                batch_delete_payload["data"]["deleted_count"] == 2
            ), f"Unexpected deleted count: {batch_delete_payload}"

            users_after_batch_delete = _admin_data(client, ADMIN_USER_ROUTE)
            assert int(users_after_batch_delete["total"]) == admin_users_total

            # Test POST /admin/RoleAdmin/add + /delete
            roles_before_payload = _admin_data(client, ROLE_ROUTE)
            roles_before_total = int(roles_before_payload["total"])
            role_name = f"role-{run_id}"
            role_add_response = client.post(
                f"/admin/{ROLE_ROUTE}/add",
                content=(
                    f"name={role_name}&description=E2E-role"
                    "&accessible_models=%5B%22AdminUserAdmin%22%5D"
                ),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert (
                role_add_response.status_code == 200
            ), f"Role add failed: {role_add_response.text}"

            roles_after_add_payload = _admin_data(client, ROLE_ROUTE)
            assert int(roles_after_add_payload["total"]) == roles_before_total + 1
            created_role_row = _find_row_by_field(
                roles_after_add_payload["data"], "name", role_name
            )
            assert created_role_row is not None, "Created role not found"
            created_role_id = str(created_role_row["data"]["id"])

            # Test POST /admin/UserRoleAdmin/add + /delete
            user_roles_before_payload = _admin_data(client, USER_ROLE_ROUTE)
            user_roles_before_total = int(user_roles_before_payload["total"])
            user_role_ids_before = {
                str(row.get("data", {}).get("id"))
                for row in user_roles_before_payload["data"]
                if row.get("data", {}).get("id") is not None
            }
            user_role_add_response = client.post(
                f"/admin/{USER_ROLE_ROUTE}/add",
                content=f"user_id={admin_id}&role_id={created_role_id}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert (
                user_role_add_response.status_code == 200
            ), f"User-role add failed: {user_role_add_response.text}"

            user_roles_after_add_payload = _admin_data(client, USER_ROLE_ROUTE)
            assert (
                int(user_roles_after_add_payload["total"])
                == user_roles_before_total + 1
            )
            user_role_ids_after = {
                str(row.get("data", {}).get("id"))
                for row in user_roles_after_add_payload["data"]
                if row.get("data", {}).get("id") is not None
            }
            created_user_role_ids = sorted(
                user_role_ids_after - user_role_ids_before
            )
            assert created_user_role_ids, "Created user-role relation not found"
            created_user_role_id = created_user_role_ids[0]

            user_role_delete_response = client.post(
                f"/admin/{USER_ROLE_ROUTE}/{created_user_role_id}/delete"
            )
            assert (
                user_role_delete_response.status_code == 200
            ), f"User-role delete failed: {user_role_delete_response.text}"
            user_roles_after_delete_payload = _admin_data(client, USER_ROLE_ROUTE)
            assert (
                int(user_roles_after_delete_payload["total"])
                == user_roles_before_total
            )

            role_delete_response = client.post(
                f"/admin/{ROLE_ROUTE}/{created_role_id}/delete"
            )
            assert (
                role_delete_response.status_code == 200
            ), f"Role delete failed: {role_delete_response.text}"
            roles_after_delete_payload = _admin_data(client, ROLE_ROUTE)
            assert int(roles_after_delete_payload["total"]) == roles_before_total

            # Test GET /admin/:route_id/inline_data (missing params)
            inline_data_response = client.get(
                f"/admin/{USER_ROLE_ROUTE}/inline_data"
            )
            assert (
                inline_data_response.status_code == 200
            ), f"Inline data request failed: {inline_data_response.text}"
            assert (
                inline_data_response.json().get("error") == "Missing parameters"
            )

            # Test POST /admin/upload (no file)
            upload_response = client.post("/admin/upload")
            assert (
                upload_response.status_code == 200
            ), f"Upload endpoint failed: {upload_response.text}"
            upload_payload = upload_response.json()
            assert upload_payload["success"] is False
            assert upload_payload["code"] == 400
            assert upload_payload["message"] == "No file uploaded"

            # Test POST /admin/:route_id/import (unsupported by default)
            import_response = client.post(f"/admin/{ADMIN_USER_ROUTE}/import")
            assert (
                import_response.status_code == 200
            ), f"Import endpoint failed: {import_response.text}"
            import_payload = import_response.json()
            assert import_payload["success"] is False
            assert import_payload["message"] == "Import is not supported"

            # Test GET /admin/logout
            logout_response = client.get("/admin/logout")
            assert (
                logout_response.status_code == 303
            ), f"Admin logout failed: {logout_response.text}"

            # === Test User endpoints ===
            create_response = client.post("/users", json=user_payload)
            create_response.raise_for_status()

            activation_key = fetch_activation_key()
            activation_response = client.post(
                "/users/activate",
                json={"key": activation_key},
            )
            if activation_response.status_code != 200:
                pytest.fail("Activation failed")

            login_response = client.post(
                "/auth/login",
                json={"login": user_payload["username"], "password": user_payload["password"]},
            )
            login_response.raise_for_status()
            login_payload = login_response.json().get("result", {})
            token = login_payload.get("accessToken")
            assert token, "Login response must expose an access token"

            me_response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            me_response.raise_for_status()
            assert me_response.json().get("result", {}).get("username") == user_payload["username"]

            # === Test Product endpoints (from add command) ===
            # Test GET /products (list)
            list_response = client.get("/products")
            assert list_response.status_code == 200, f"GET /products failed: {list_response.text}"
            result = list_response.json().get("result", [])
            assert isinstance(result, list), "Expected list response"

            # Test POST /products (create)
            product_payload = {"name": "Test Product"}
            create_product_response = client.post("/products", json=product_payload)
            assert create_product_response.status_code == 201, f"POST /products failed: {create_product_response.text}"
            created_product = create_product_response.json().get("result", {})
            product_id = created_product.get("id")
            assert product_id, "Created product should have an ID"
            assert created_product.get("name") == "Test Product"

            # Test GET /products/:id (get single)
            get_response = client.get(f"/products/{product_id}")
            assert get_response.status_code == 200, f"GET /products/{product_id} failed: {get_response.text}"
            fetched_product = get_response.json().get("result", {})
            assert fetched_product.get("id") == product_id
            assert fetched_product.get("name") == "Test Product"

            # Test PUT /products/:id (update)
            update_payload = {"name": "Updated Product"}
            update_response = client.put(f"/products/{product_id}", json=update_payload)
            assert update_response.status_code == 200, f"PUT /products/{product_id} failed: {update_response.text}"
            updated_product = update_response.json().get("result", {})
            assert updated_product.get("name") == "Updated Product"

            # Test DELETE /products/:id (delete)
            delete_response = client.delete(f"/products/{product_id}")
            assert delete_response.status_code in [200, 204], f"DELETE /products/{product_id} failed: {delete_response.text}"

            # Verify deletion - GET should fail
            get_deleted_response = client.get(f"/products/{product_id}")
            assert get_deleted_response.status_code in [404, 500], "Deleted product should not be found"

    finally:
        if compose_started:
            docker_compose(
                project_dir,
                "down",
                "-v",
                "--remove-orphans",
            )
