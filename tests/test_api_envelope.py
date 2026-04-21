from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from prep.api.envelope import ApiException, install_api_exception_handlers


def test_api_exception_enveloped() -> None:
    app = FastAPI()
    install_api_exception_handlers(app)

    @app.get("/boom")
    def boom() -> dict:
        raise ApiException(status_code=404, code="PROJECT_NOT_FOUND", message="nope")

    client = TestClient(app)
    res = client.get("/boom")
    assert res.status_code == 404

    body = res.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "PROJECT_NOT_FOUND"
    assert body["error"]["message"] == "nope"


def test_validation_error_enveloped() -> None:
    app = FastAPI()
    install_api_exception_handlers(app)

    @app.post("/needs-body")
    def needs_body(payload: dict) -> dict:
        return payload

    client = TestClient(app)
    res = client.post("/needs-body", data="not-json")
    assert res.status_code == 400

    body = res.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"
