import json

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
