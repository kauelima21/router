import importlib
import logging
import re

from router.contracts.http import Request, Response

logger = logging.getLogger(__name__)

_PATH_PARAM_RE = re.compile(r"\{([^}/]+)\}")


class Router:
    """
    Router class to handle route mappings.

    example usage:
    router = Router()

    # callable handler (function, static method, lambda)
    router.get("/health", lambda req, res: res.json({"ok": True}))

    # string handler with namespace - auto-instantiates and binds the method
    router.namespace("controllers.auth")
    router.group("auth")
    router.post("/sign-in", "AuthController:sign_in")
    router.post("/sign-up", "AuthController:sign_up")

    router.dispatch(lambda_event)
    """
    def __init__(self, silent: bool = False, api_version: str = "auto"):
        self.routes = {}
        self._group = ""
        self._group_middleware = []
        self._namespace = None
        self._silent = silent
        self._api_version = api_version
        self._error_code = None

    def _resolve_handler(self, handler):
        if callable(handler):
            return handler

        if not isinstance(handler, str):
            raise TypeError("Handler must be a callable or a string in 'Class:method' format.")

        if self._namespace is None:
            raise RuntimeError(
                f"Cannot use string handler '{handler}' without an active namespace. "
                "Call router.namespace('module.path') first."
            )

        if ":" not in handler:
            raise ValueError(f"Invalid handler string '{handler}'. Expected 'Class:method' format.")

        class_name, method_name = handler.split(":", 1)
        module = importlib.import_module(self._namespace)
        cls = getattr(module, class_name)
        instance = cls()
        return getattr(instance, method_name)

    @staticmethod
    def _normalize_middleware(middleware):
        if middleware is None:
            return []
        if callable(middleware):
            return [middleware]
        return list(middleware)

    def _add_route(self, method: str, path: str, handler, middleware=None):
        resolved = self._resolve_handler(handler)
        middlewares = self._group_middleware + self._normalize_middleware(middleware)

        if self._group:
            path = f"/{self._group}{path}"
        self.routes[method, path] = (resolved, middlewares, self._compile_path(path))

    @staticmethod
    def _compile_path(path: str):
        """Compile a route template like ``/users/{id}`` into a regex that
        captures each path parameter by name. Returned value is used as a
        fallback when the registered routeKey on the event does not match the
        actual raw path — notably when API Gateway integrates via a catch-all
        ``/{proxy+}`` route.
        """
        regex = _PATH_PARAM_RE.sub(r"(?P<\1>[^/]+)", path)
        return re.compile(f"^{regex}$")

    def _resolve_route(self, method: str, path: str, raw_path: str):
        """Resolve a registered route for the given request.

        Strategy:
        1. Try an exact ``(method, path)`` lookup — fast path for events where
           the routeKey already carries the route template.
        2. Fall back to matching ``raw_path`` against every registered route's
           compiled pattern. This makes catch-all integrations work: when
           API Gateway sends ``routeKey="ANY /{proxy+}"``, path ends up as
           ``/{proxy+}`` but ``raw_path`` is the concrete URL.

        Returns one of:
        - ``(handler, middlewares, template, params)`` on match.
        - ``"method_not_allowed"`` when path matches but method does not.
        - ``None`` when nothing matches.
        """
        direct = self.routes.get((method, path))
        if direct is not None:
            handler, middlewares, _ = direct
            return handler, middlewares, path, {}

        method_mismatch = False
        for (route_method, template), (handler, middlewares, pattern) in self.routes.items():
            match = pattern.match(raw_path)
            if not match:
                continue
            if route_method == method:
                return handler, middlewares, template, match.groupdict()
            method_mismatch = True

        if method_mismatch:
            return "method_not_allowed"
        return None

    def _run_with_middleware(self, handler, middlewares, request, response):
        if not middlewares:
            return handler(request, response)

        def make_next(index):
            if index >= len(middlewares):
                return lambda req, res: handler(req, res)
            return lambda req, res: middlewares[index](req, res, make_next(index + 1))

        return make_next(0)(request, response)

    def dispatch(self, event: dict):
        self._error_code = None
        response = Response()

        try:
            request = Request(event, api_version=self._api_version)
        except (KeyError, TypeError, ValueError) as exc:
            if not self._silent:
                logger.warning("Bad request: %s", exc)
            self._error_code = 400
            return response.status(400).send("Bad Request")

        method = request.method
        path = request.path
        raw_path = request.raw_path

        resolved = self._resolve_route(method, path, raw_path)

        if resolved == "method_not_allowed":
            if not self._silent:
                logger.warning("Method not allowed: %s %s", method, raw_path or path)
            self._error_code = 405
            return response.status(405).send("Method Not Allowed")

        if resolved is None:
            if not self._silent:
                logger.warning("Route not found: %s %s", method, raw_path or path)
            self._error_code = 404
            return response.status(404).send("Not Found")

        handler, middlewares, matched_template, extra_params = resolved

        if extra_params:
            request.path = matched_template
            request.params = {**(request.params or {}), **extra_params}

        try:
            return self._run_with_middleware(handler, middlewares, request, response)
        except NotImplementedError as exc:
            if not self._silent:
                logger.error(
                    "Controller not implemented on %s %s: %s", method, matched_template, exc
                )
            self._error_code = 501
            return response.status(501).send("Not Implemented")
        except Exception as exc:
            if not self._silent:
                logger.error("Handler error on %s %s: %s", method, matched_template, exc)
            self._error_code = 500
            return response.status(500).json({"error": "Internal Server Error"})

    def namespace(self, module_path: str | None):
        self._namespace = module_path
        return self

    def group(self, group: str | None, middleware=None):
        self._group = group
        self._group_middleware = self._normalize_middleware(middleware)
        return self

    def error(self) -> int | None:
        """Returns the HTTP status code of the most recent dispatch error
        (400/404/405/500/501), or ``None`` if the last dispatch succeeded.

        Use after ``dispatch()`` to decide whether to redirect to an error
        page:

            result = router.dispatch(event)
            if (code := router.error()):
                return Response().redirect(f"/ooops/{code}")
            return result
        """
        return self._error_code

    def get(self, path: str, handler, middleware=None):
        self._add_route("GET", path, handler, middleware)

    def post(self, path: str, handler, middleware=None):
        self._add_route("POST", path, handler, middleware)

    def put(self, path: str, handler, middleware=None):
        self._add_route("PUT", path, handler, middleware)

    def delete(self, path: str, handler, middleware=None):
        self._add_route("DELETE", path, handler, middleware)

    def patch(self, path: str, handler, middleware=None):
        self._add_route("PATCH", path, handler, middleware)

    def options(self, path: str, handler, middleware=None):
        self._add_route("OPTIONS", path, handler, middleware)

    def head(self, path: str, handler, middleware=None):
        self._add_route("HEAD", path, handler, middleware)
