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
