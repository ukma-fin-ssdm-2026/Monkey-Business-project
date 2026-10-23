"""
Регресійні тести для CWE-209: відповідь 422 не повертає тіло запиту чи значення
чутливих полів (docs/code-quality/static-analysis.md, знахідка 3).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.errors import register_error_handlers
from src.api.schemas import ChangePasswordRequest, LoginRequest, RegisterRequest

SECRET = "s3cret-Passw0rd" # pragma: allowlist secret


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/login")
    def login(payload: LoginRequest) -> dict:
        return {}

    @app.post("/register")
    def register(payload: RegisterRequest) -> dict:
        return {}

    @app.post("/change-password")
    def change_password(payload: ChangePasswordRequest) -> dict:
        return {}

    return TestClient(app)


def _details(response) -> dict:
    assert response.status_code == 422
    return {d["field"]: d for d in response.json()["error"]["details"]}


def test_missing_field_does_not_echo_request_body(client):
    response = client.post("/login", json={"password": SECRET})

    assert SECRET not in response.text
    assert _details(response)["email"]["provided_value"] is None


@pytest.mark.parametrize(
    "path, payload, field",
    [
        ("/register", {"email": "a@example.com", "password": "short1"}, "password"), # pragma: allowlist secret
        (
            "/change-password",
            {"current_password": SECRET, "new_password": "short1"}, # pragma: allowlist secret
            "new_password",
        ),
    ],
)
def test_invalid_sensitive_value_is_not_echoed(client, path, payload, field):
    response = client.post(path, json=payload)

    assert "short1" not in response.text
    assert _details(response)[field]["provided_value"] is None


def test_long_value_is_truncated(client):
    response = client.post("/login", json={"email": "x" * 5000, "password": SECRET})

    assert len(_details(response)["email"]["provided_value"]) <= 100


def test_invalid_non_sensitive_value_is_still_returned(client):
    response = client.post("/login", json={"email": "not-an-email", "password": SECRET})

    assert _details(response)["email"]["provided_value"] == "not-an-email"
