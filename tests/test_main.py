"""
Інструмент: Claude
Застосування: Юніт-тести для src/api/main.py — health-ендпоінт і автогенерація
OpenAPI YAML при старті застосунку.
"""

from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from src.api import main as main_module


def test_health_returns_ok():
    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_save_openapi_spec_writes_yaml_file(tmp_path, monkeypatch):
    spec_path = tmp_path / "openapi-generated.yaml"
    monkeypatch.setattr(main_module, "SPEC_PATH", spec_path)

    main_module.save_openapi_spec(main_module.app)

    assert spec_path.exists()
    loaded = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert loaded["info"]["title"] == "Tech Interview Board API"


def test_save_openapi_spec_creates_missing_parent_dirs(tmp_path, monkeypatch):
    spec_path = tmp_path / "nested" / "dir" / "openapi.yaml"
    monkeypatch.setattr(main_module, "SPEC_PATH", spec_path)

    main_module.save_openapi_spec(main_module.app)

    assert spec_path.exists()


def test_lifespan_generates_spec_on_startup(tmp_path, monkeypatch):
    spec_path = tmp_path / "openapi-generated.yaml"
    monkeypatch.setattr(main_module, "SPEC_PATH", spec_path)

    with TestClient(main_module.app):
        pass

    assert spec_path.exists()