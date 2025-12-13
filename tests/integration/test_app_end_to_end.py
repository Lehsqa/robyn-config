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


def wait_for_health(timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{APP_BASE_URL}/health", timeout=5.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    pytest.fail("App health check did not become available in time")


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
    run_make_migration(project_dir, design, orm)
    shutil.copy2(project_dir / ".env.example", project_dir / ".env")

    compose_started = False
    try:
        docker_compose(project_dir, "up", "-d", "--build")
        compose_started = True
        wait_for_health()
        clear_mailhog_queue()

        user_payload = {
            "username": "user",
            "email": "user@email.com",
            "password": "12Qwerty%",
        }
        with httpx.Client(base_url=APP_BASE_URL, timeout=10.0) as client:
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
