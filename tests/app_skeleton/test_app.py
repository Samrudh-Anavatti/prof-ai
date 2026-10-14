from fastapi.testclient import TestClient

from prof_ai.config import Settings
from prof_ai.main import create_app


def client_for(app_env: str) -> TestClient:
    return TestClient(create_app(Settings(app_env=app_env)))


def test_healthz_contract():
    response = client_for("production").get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_landing_page_is_html():
    response = client_for("production").get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_api_docs_disabled_in_production():
    client = client_for("production")
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_api_docs_available_locally():
    assert client_for("local").get("/docs").status_code == 200
