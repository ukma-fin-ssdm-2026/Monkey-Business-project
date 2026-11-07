"""R10: optional OpenAPI export must not prevent API startup.

Використання ШІ: Codex — ін'єкція файлових збоїв, перевірка доступності
API, відновлення експорту та меж обробки винятків.
"""

import errno
import logging
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.api import main


@pytest.mark.parametrize("error_number", [errno.EACCES, errno.EROFS, errno.ENOSPC])
def test_api_starts_and_recovers_after_openapi_write_failure(
    monkeypatch, tmp_path, session_factory, caplog, error_number
):
    spec_path = tmp_path / "openapi.yaml"
    monkeypatch.setattr(main, "SPEC_PATH", spec_path)
    original_open = Path.open

    def failed_open(path, *args, **kwargs):
        if path == spec_path:
            raise OSError(error_number, "Injected filesystem failure")
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(Path, "open", failed_open)
        with caplog.at_level(logging.WARNING, logger=main.__name__):
            with TestClient(main.app) as client:
                assert client.get("/health").status_code == 200
                response = client.get("/openapi.json")
                assert response.status_code == 200
                assert "/v1/auth/login" in response.json()["paths"]
                assert client.get("/api-docs").status_code == 200
                # A real API route still handles requests through the DB.
                assert (
                    client.post(
                        "/v1/auth/login",
                        json={
                            "email": "absent@example.com",
                            "password": "test-pass-123",  # pragma: allowlist secret
                        },
                    ).status_code
                    == 401
                )

    assert not spec_path.exists()
    assert any(
        record.name == main.__name__
        and record.levelno == logging.WARNING
        and "OpenAPI" in record.getMessage()
        and record.exc_info is not None
        for record in caplog.records
    )

    # Once storage is available again, the next startup exports a valid file.
    with TestClient(main.app):
        pass
    exported = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert exported == response.json()


def test_api_starts_when_spec_parent_is_a_file(monkeypatch, tmp_path, session_factory):
    parent = tmp_path / "not-a-directory"
    parent.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr(main, "SPEC_PATH", parent / "openapi.yaml")

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/openapi.json").status_code == 200
    assert parent.read_text(encoding="utf-8") == "occupied"


def test_startup_does_not_hide_schema_programming_errors(monkeypatch):
    def broken_schema():
        raise ValueError("Invalid schema")

    monkeypatch.setattr(main.app, "openapi", broken_schema)
    with pytest.raises(ValueError, match="Invalid schema"):
        with TestClient(main.app):
            pass


def test_explicit_export_still_fails_when_destination_is_invalid(monkeypatch, tmp_path):
    parent = tmp_path / "not-a-directory"
    parent.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr(main, "SPEC_PATH", parent / "openapi.yaml")

    # The CLI/CI export must report failure instead of silently using an old file.
    with pytest.raises(OSError):
        main.save_openapi_spec(main.app)
