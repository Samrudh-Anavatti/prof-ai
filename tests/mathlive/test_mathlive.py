import pytest
from fastapi.testclient import TestClient

from prof_ai.chat.checking import matches_key
from prof_ai.config import Settings
from prof_ai.main import create_app

FONT = "assets/mathlive/fonts/KaTeX_Main-Regular.woff2"


def client_for(tmp_path) -> TestClient:
    static_dir = tmp_path / "static"
    (static_dir / FONT).parent.mkdir(parents=True)
    (static_dir / "index.html").write_text("<!doctype html><div id=root></div>")
    (static_dir / FONT).write_bytes(b"wOF2")
    return TestClient(create_app(Settings(app_env="production"), static_dir=static_dir))


def directives(csp: str) -> dict[str, str]:
    pairs = (d.strip().split(" ", 1) for d in csp.split(";") if d.strip())
    return {name: value for name, value in pairs}


def test_only_inline_style_attributes_are_allowed(tmp_path):
    policy = directives(client_for(tmp_path).get("/").headers["content-security-policy"])
    assert policy["style-src-attr"] == "'unsafe-inline'"
    assert policy["style-src"] == "'self'"
    assert policy["script-src"] == "'self'"
    assert policy["default-src"] == "'self'"
    assert "style-src-elem" not in policy
    assert all("unsafe" not in v for k, v in policy.items() if k != "style-src-attr")


def test_maths_fonts_are_served_from_our_own_assets(tmp_path):
    response = client_for(tmp_path).get(f"/{FONT}")
    assert response.status_code == 200
    assert response.content == b"wOF2"


@pytest.mark.parametrize(
    ("answer", "key"),
    [
        (r"$x=2\:\mathrm{or}\:x=3$", "x = 2 or x = 3"),
        (r"$x=2\text{ or }x=3$", "x = 2 or x = 3"),
        (r"$\left(x-2\right)\left(x-3\right)=0$", "(x - 2)(x - 3) = 0"),
        (r"$10\text{ km}$", "10 km"),
    ],
)
def test_a_maths_field_answer_matches_a_typed_key(answer, key):
    assert matches_key(answer, key)


def test_words_still_count_when_matching():
    assert not matches_key(r"$x=2\:\mathrm{and}\:x=3$", "x = 2 or x = 3")
