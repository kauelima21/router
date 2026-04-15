import base64
import json

from router.contracts.http import Request
from tests.conftest import make_event, make_v1_event


# --- Parsing basico ---

def test_parses_method_and_path(event_factory):
    req = Request(event_factory("POST", "/users"))

    assert req.method == "POST"
    assert req.path == "/users"


def test_parses_json_body(event_factory):
    req = Request(event_factory(body='{"name": "Kaue"}'))

    assert req.body == {"name": "Kaue"}
    assert req.raw_body == '{"name": "Kaue"}'


def test_parses_query_string(event_factory):
    req = Request(event_factory(query={"page": "2"}))

    assert req.query == {"page": "2"}


def test_parses_path_parameters(event_factory):
    req = Request(event_factory(params={"id": "42"}))

    assert req.params == {"id": "42"}


def test_parses_authenticated_user(event_factory):
    claims = {"sub": "user-123", "email": "kaue@test.com"}
    req = Request(event_factory(claims=claims))

    assert req.authenticated_user["sub"] == "user-123"


def test_authenticated_user_empty_when_no_authorizer(event_factory):
    req = Request(event_factory())

    assert req.authenticated_user == {}


# --- Edge cases corrigidos ---

def test_default_route_key_uses_raw_path(event_factory):
    req = Request(event_factory(route_key="$default", path="/fallback"))

    assert req.path == "/fallback"


def test_query_none_becomes_empty_dict():
    event = make_event()
    event["queryStringParameters"] = None
    req = Request(event)

    assert req.query == {}


def test_params_none_becomes_empty_dict():
    event = make_event()
    event["pathParameters"] = None
    req = Request(event)

    assert req.params == {}


def test_body_none_becomes_empty_dict():
    event = make_event()
    event["body"] = None
    req = Request(event)

    assert req.body == {}
    assert req.raw_body == ""


def test_body_invalid_json_becomes_empty_dict(event_factory):
    req = Request(event_factory(body="not json"))

    assert req.body == {}
    assert req.raw_body == "not json"


def test_body_absent_becomes_empty_dict(event_factory):
    req = Request(event_factory())

    assert req.body == {}
    assert req.raw_body == ""


# --- API Gateway v1 (REST API) ---

def test_v1_parses_method_and_path():
    req = Request(make_v1_event("POST", "/users"))

    assert req.method == "POST"
    assert req.path == "/users"


def test_v1_parses_resource_as_path():
    req = Request(make_v1_event("GET", "/users/42", resource="/users/{id}"))

    assert req.path == "/users/{id}"
    assert req.raw_path == "/users/42"


def test_v1_parses_json_body():
    req = Request(make_v1_event(body='{"name": "Kaue"}'))

    assert req.body == {"name": "Kaue"}


def test_v1_parses_authenticated_user():
    claims = {"sub": "user-456", "email": "kaue@test.com"}
    req = Request(make_v1_event(claims=claims))

    assert req.authenticated_user["sub"] == "user-456"


def test_v1_authenticated_user_empty_when_no_authorizer():
    req = Request(make_v1_event())

    assert req.authenticated_user == {}


def test_v1_query_none_becomes_empty_dict():
    event = make_v1_event()
    event["queryStringParameters"] = None
    req = Request(event)

    assert req.query == {}


def test_v1_body_invalid_json_becomes_empty_dict():
    req = Request(make_v1_event(body="not json"))

    assert req.body == {}


# --- Auto-detect ---

def test_auto_detects_v2_by_route_key():
    event = make_event("GET", "/items")
    req = Request(event)

    assert req.method == "GET"
    assert req.path == "/items"


def test_auto_detects_v1_by_http_method():
    event = make_v1_event("DELETE", "/items/1")
    req = Request(event)

    assert req.method == "DELETE"
    assert req.path == "/items/1"


def test_explicit_v1_override():
    event = make_v1_event("PUT", "/items/1")
    req = Request(event, api_version="v1")

    assert req.method == "PUT"


def test_explicit_v2_override():
    event = make_event("PATCH", "/items/1")
    req = Request(event, api_version="v2")

    assert req.method == "PATCH"


# --- to_dict ---

def test_to_dict_roundtrip(event_factory):
    req = Request(event_factory("GET", "/items", query={"q": "test"}))
    d = req.to_dict()

    assert d["method"] == "GET"
    assert d["path"] == "/items"
    assert d["queryStringParameters"] == {"q": "test"}


# --- Multipart form-data ---

BOUNDARY = "----TestBoundary"


def _build_multipart(*parts) -> bytes:
    body = b""
    for part in parts:
        body += f"--{BOUNDARY}\r\n".encode()
        body += part
    body += f"--{BOUNDARY}--\r\n".encode()
    return body


def _text_part(name: str, value: str) -> bytes:
    return (
        f'Content-Disposition: form-data; name="{name}"\r\n'
        f"\r\n"
        f"{value}\r\n"
    ).encode()


def _file_part(name: str, filename: str, content_type: str, data: bytes) -> bytes:
    header = (
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n"
        f"\r\n"
    ).encode()
    return header + data + b"\r\n"


def test_multipart_parses_text_fields():
    body = _build_multipart(
        _text_part("title", "Meu Evento"),
        _text_part("date", "2026-05-01"),
    )
    event = make_event(
        "POST", "/upload",
        body=body.decode("latin-1"),
        headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"},
    )
    req = Request(event)

    assert req.body == {"title": "Meu Evento", "date": "2026-05-01"}
    assert req.files == {}


def test_multipart_parses_file():
    file_data = b"\x89PNG\r\n\x1a\n\x00\x00"
    body = _build_multipart(
        _file_part("banner", "foto.png", "image/png", file_data),
    )
    encoded = base64.b64encode(body).decode()
    event = make_event(
        "POST", "/upload",
        body=encoded,
        headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"},
    )
    event["isBase64Encoded"] = True
    req = Request(event)

    assert "banner" in req.files
    assert req.files["banner"]["filename"] == "foto.png"
    assert req.files["banner"]["content_type"] == "image/png"
    assert req.files["banner"]["body"] == file_data


def test_multipart_parses_fields_and_files():
    file_data = b"\xff\xd8\xff\xe0"
    body = _build_multipart(
        _text_part("event_id", "42"),
        _file_part("file", "banner.jpg", "image/jpeg", file_data),
    )
    encoded = base64.b64encode(body).decode()
    event = make_event(
        "POST", "/upload",
        body=encoded,
        headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"},
    )
    event["isBase64Encoded"] = True
    req = Request(event)

    assert req.body == {"event_id": "42"}
    assert req.files["file"]["filename"] == "banner.jpg"
    assert req.files["file"]["body"] == file_data


def test_non_multipart_request_has_empty_files():
    req = Request(make_event("GET", "/events"))

    assert req.files == {}
