import json

import pytest

from router.contracts.http import Response


def test_default_status_is_200():
    res = Response()

    assert res.status_code == 200


def test_status_sets_code():
    result = Response().status(201).json({"id": 1})

    assert result["statusCode"] == 201


def test_send_returns_text_plain():
    result = Response().send("hello")

    assert result["body"] == "hello"
    assert result["headers"]["Content-Type"] == "text/plain"


def test_send_preserves_custom_content_type():
    result = Response().set("Content-Type", "text/html").send("<h1>Hi</h1>")

    assert result["headers"]["Content-Type"] == "text/html"


def test_json_returns_application_json():
    result = Response().json({"key": "value"})

    assert result["headers"]["Content-Type"] == "application/json"
    assert json.loads(result["body"]) == {"key": "value"}


def test_json_with_list():
    result = Response().json([1, 2, 3])

    assert json.loads(result["body"]) == [1, 2, 3]


def test_html_returns_text_html():
    result = Response().html("<h1>Hello</h1>")

    assert result["statusCode"] == 200
    assert result["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert result["body"] == "<h1>Hello</h1>"


def test_set_header():
    result = Response().set("X-Custom", "abc").send("ok")

    assert result["headers"]["X-Custom"] == "abc"


def test_cookie():
    result = Response().cookie("session=abc; HttpOnly").json({})

    assert "session=abc; HttpOnly" in result["cookies"]


def test_multiple_cookies():
    result = (
        Response()
        .cookie("a=1")
        .cookie("b=2")
        .json({})
    )

    assert result["cookies"] == ["a=1", "b=2"]


def test_finalize_omits_body_when_none():
    res = Response()
    result = res._finalize()

    assert "body" not in result


def test_finalize_includes_base64_flag():
    result = Response().send("ok")

    assert result["isBase64Encoded"] is False


def test_redirect_default_is_303():
    result = Response().redirect("/login")

    assert result["statusCode"] == 303
    assert result["headers"]["Location"] == "/login"
    assert "body" not in result


def test_redirect_permanent():
    result = Response().redirect("https://example.com", 301)

    assert result["statusCode"] == 301
    assert result["headers"]["Location"] == "https://example.com"


def test_redirect_rejects_non_3xx():
    with pytest.raises(ValueError, match="redirect status must be 3xx"):
        Response().redirect("/login", 200)


def test_redirect_method_get_forces_303():
    result = Response().redirect("/list", method="GET")

    assert result["statusCode"] == 303
    assert result["headers"]["Location"] == "/list"


def test_redirect_method_post_preserves_with_307():
    result = Response().redirect("/items", method="POST")

    assert result["statusCode"] == 307


def test_redirect_method_lowercase_is_normalized():
    result = Response().redirect("/list", method="get")

    assert result["statusCode"] == 303


def test_redirect_method_overrides_status_code():
    """Explicit status_code is overridden when method is given."""
    result = Response().redirect("/x", status_code=301, method="GET")

    assert result["statusCode"] == 303


def test_redirect_method_put_uses_307():
    result = Response().redirect("/x", method="PUT")

    assert result["statusCode"] == 307
