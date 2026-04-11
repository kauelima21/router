import logging

import pytest

from router import Router
from tests.conftest import make_event, make_v1_event


# --- Registro de rotas ---

def test_add_route(router):
    handler = lambda req, res: res.json({"ok": True})
    router.get("/items", handler)

    assert ("GET", "/items") in router.routes


def test_add_route_rejects_non_callable(router):
    with pytest.raises(TypeError, match="Handler must be a callable"):
        router.add_route("GET", "/bad", "not_a_function")


# --- Dispatch ---

def test_dispatch_calls_handler(router, event_factory):
    def handler(req, res):
        return res.status(200).json({"called": True})

    router.get("/ping", handler)
    result = router.dispatch(event_factory("GET", "/ping"))

    assert result["statusCode"] == 200
    assert '"called": true' in result["body"]


def test_dispatch_returns_404_when_not_found(router, event_factory):
    result = router.dispatch(event_factory("GET", "/missing"))

    assert result["statusCode"] == 404
    assert result["body"] == "Not Found"


def test_dispatch_returns_500_on_handler_exception(router, event_factory):
    def bad_handler(req, res):
        raise ValueError("boom")

    router.get("/explode", bad_handler)
    result = router.dispatch(event_factory("GET", "/explode"))

    assert result["statusCode"] == 500
    assert '"error"' in result["body"]


def test_dispatch_logs_warning_on_404(router, event_factory, caplog):
    with caplog.at_level(logging.WARNING):
        router.dispatch(event_factory("GET", "/nope"))

    assert "Route not found: GET /nope" in caplog.text


def test_dispatch_logs_error_on_500(router, event_factory, caplog):
    def bad_handler(req, res):
        raise RuntimeError("fail")

    router.get("/fail", bad_handler)

    with caplog.at_level(logging.ERROR):
        router.dispatch(event_factory("GET", "/fail"))

    assert "Handler error on GET /fail" in caplog.text


def test_dispatch_silent_suppresses_logs(event_factory, caplog):
    silent_router = Router(silent=True)
    silent_router.get("/x", lambda req, res: (_ for _ in ()).throw(Exception("err")))

    with caplog.at_level(logging.DEBUG):
        silent_router.dispatch(event_factory("GET", "/missing"))
        silent_router.dispatch(event_factory("GET", "/x"))

    assert caplog.text == ""


# --- Group ---

def test_group_prefixes_routes(router):
    router.group("admin")
    router.get("/users", lambda req, res: None)

    assert ("GET", "/admin/users") in router.routes


def test_group_none_resets_prefix(router):
    router.group("v1")
    router.get("/a", lambda req, res: None)
    router.group(None)
    router.get("/b", lambda req, res: None)

    assert ("GET", "/v1/a") in router.routes
    assert ("GET", "/b") in router.routes


# --- API Gateway v1 dispatch ---

def test_dispatch_v1_event():
    router = Router(api_version="v1")

    def handler(req, res):
        return res.json({"user": req.params.get("id")})

    router.get("/users/{id}", handler)
    event = make_v1_event("GET", "/users/42", resource="/users/{id}", params={"id": "42"})
    result = router.dispatch(event)

    assert result["statusCode"] == 200
    assert '"user": "42"' in result["body"]


def test_dispatch_v1_404():
    router = Router(api_version="v1")
    event = make_v1_event("GET", "/missing")
    result = router.dispatch(event)

    assert result["statusCode"] == 404


def test_dispatch_auto_detect_v1():
    router = Router()

    def handler(req, res):
        return res.json({"ok": True})

    router.get("/health", handler)
    event = make_v1_event("GET", "/health")
    result = router.dispatch(event)

    assert result["statusCode"] == 200


# --- Metodos HTTP ---

def test_all_http_methods(router):
    handler = lambda req, res: None

    router.get("/r", handler)
    router.post("/r", handler)
    router.put("/r", handler)
    router.delete("/r", handler)
    router.patch("/r", handler)
    router.options("/r", handler)
    router.head("/r", handler)

    for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
        assert (method, "/r") in router.routes
