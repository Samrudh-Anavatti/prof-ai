import re

import pytest
from fastapi.testclient import TestClient

from prof_ai.config import Settings
from prof_ai.main import create_app

SHELL = '<!doctype html><html><body><div id="root"></div></body></html>'


@pytest.fixture
def built_dir(tmp_path):
    static_dir = tmp_path / "static"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text(SHELL)
    (static_dir / "assets" / "index-abc123.js").write_text("console.log('app')")
    (tmp_path / "secret.txt").write_text("not for you")
    return static_dir


def client_for(static_dir, app_env="production") -> TestClient:
    return TestClient(create_app(Settings(app_env=app_env), static_dir=static_dir))


@pytest.mark.parametrize("path", ["/", "/assignments", "/tutor/students/oid-1"])
def test_client_routes_get_the_app_shell(built_dir, path):
    response = client_for(built_dir).get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == SHELL
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("path", ["/api", "/api/nope", "/assets/missing.js", "/favicon.ico"])
def test_unknown_api_and_file_paths_are_json_404s(built_dir, path):
    response = client_for(built_dir).get(path)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_assets_are_served_with_long_cache(built_dir):
    response = client_for(built_dir).get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"
    assert "immutable" in response.headers["cache-control"]


@pytest.mark.parametrize(
    "path", ["/assets/../secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt", "/assets/..%2fsecret.txt"]
)
def test_assets_refuse_path_traversal(built_dir, path):
    response = client_for(built_dir).get(path)
    assert response.status_code == 404
    assert "not for you" not in response.text


def test_shell_has_strict_security_headers(built_dir):
    headers = client_for(built_dir).get("/").headers
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "same-origin"


def test_unbuilt_frontend_serves_a_fallback_page(tmp_path):
    response = client_for(tmp_path / "missing").get("/")
    assert response.status_code == 200
    assert "npm run build" in response.text


def test_api_docs_stay_hidden_in_production(built_dir):
    client = client_for(built_dir)
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_every_api_operation_requires_sign_in(built_dir):
    client = client_for(built_dir, app_env="local")
    operations = [
        (method, re.sub(r"\{[^}]+\}", "x", path))
        for path, item in client.get("/openapi.json").json()["paths"].items()
        if path.startswith("/api/")
        for method in item
    ]
    assert operations
    for method, path in operations:
        response = client.request(method, path)
        assert response.status_code == 401, f"{method.upper()} {path} doesn't require sign-in"
