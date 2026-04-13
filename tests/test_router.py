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
    with pytest.raises(TypeError, match="Handler must be a callable or a string"):
        router.get("/bad", 12345)


def test_add_route_string_without_namespace_raises(router):
    with pytest.raises(RuntimeError, match="without an active namespace"):
        router.get("/bad", "FakeController:index")


def test_add_route_string_without_colon_raises(router):
    router.namespace("tests.fake_controller")
    with pytest.raises(ValueError, match="Expected 'Class:method' format"):
        router.get("/bad", "index_only")


def test_add_route_with_string_handler(router, event_factory):
    router.namespace("tests.fake_controller")
    router.get("/test", "FakeController:index")

    result = router.dispatch(event_factory("GET", "/test"))
    assert result["statusCode"] == 200
    assert '"handler": "index"' in result["body"]


def test_add_route_with_string_handler_in_group(router, event_factory):
    router.namespace("tests.fake_controller")
    router.group("api")
    router.post("/items", "FakeController:create")

    result = router.dispatch(event_factory("POST", "/api/items"))
    assert result["statusCode"] == 201
    assert '"handler": "create"' in result["body"]


def test_namespace_none_resets(router):
    router.namespace("tests.fake_controller")
    router.get("/a", "FakeController:index")

    router.namespace(None)
    with pytest.raises(RuntimeError, match="without an active namespace"):
        router.get("/b", "FakeController:index")


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


# --- Middleware ---

def test_single_middleware_on_route(router, event_factory):
    def add_header(req, res, next_fn):
        res.headers["X-Custom"] = "yes"
        return next_fn(req, res)

    router.get("/m", lambda req, res: res.json({"ok": True}), middleware=add_header)
    result = router.dispatch(event_factory("GET", "/m"))

    assert result["statusCode"] == 200
    assert result["headers"]["X-Custom"] == "yes"


def test_middleware_list_on_route(router, event_factory):
    calls = []

    def mw1(req, res, next_fn):
        calls.append("mw1")
        return next_fn(req, res)

    def mw2(req, res, next_fn):
        calls.append("mw2")
        return next_fn(req, res)

    router.get("/m", lambda req, res: res.json({"ok": True}), middleware=[mw1, mw2])
    router.dispatch(event_factory("GET", "/m"))

    assert calls == ["mw1", "mw2"]


def test_middleware_can_short_circuit(router, event_factory):
    def block(req, res, next_fn):
        return res.status(403).json({"error": "Forbidden"})

    router.get("/secret", lambda req, res: res.json({"ok": True}), middleware=block)
    result = router.dispatch(event_factory("GET", "/secret"))

    assert result["statusCode"] == 403


def test_group_middleware(router, event_factory):
    calls = []

    def auth(req, res, next_fn):
        calls.append("auth")
        return next_fn(req, res)

    router.group("admin", middleware=auth)
    router.get("/users", lambda req, res: res.json({"ok": True}))

    result = router.dispatch(event_factory("GET", "/admin/users"))
    assert result["statusCode"] == 200
    assert calls == ["auth"]


def test_group_middleware_list(router, event_factory):
    calls = []

    def auth(req, res, next_fn):
        calls.append("auth")
        return next_fn(req, res)

    def log(req, res, next_fn):
        calls.append("log")
        return next_fn(req, res)

    router.group("api", middleware=[auth, log])
    router.get("/items", lambda req, res: res.json({"ok": True}))

    router.dispatch(event_factory("GET", "/api/items"))
    assert calls == ["auth", "log"]


def test_group_middleware_combined_with_route_middleware(router, event_factory):
    calls = []

    def group_mw(req, res, next_fn):
        calls.append("group")
        return next_fn(req, res)

    def route_mw(req, res, next_fn):
        calls.append("route")
        return next_fn(req, res)

    router.group("api", middleware=group_mw)
    router.get("/items", lambda req, res: res.json({"ok": True}), middleware=route_mw)

    router.dispatch(event_factory("GET", "/api/items"))
    assert calls == ["group", "route"]


def test_group_none_resets_middleware(router, event_factory):
    calls = []

    def auth(req, res, next_fn):
        calls.append("auth")
        return next_fn(req, res)

    router.group("admin", middleware=auth)
    router.get("/users", lambda req, res: res.json({"ok": True}))

    router.group(None)
    router.get("/public", lambda req, res: res.json({"ok": True}))

    router.dispatch(event_factory("GET", "/public"))
    assert calls == []
