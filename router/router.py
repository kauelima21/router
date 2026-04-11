import logging

from router.contracts.http import Request, Response

logger = logging.getLogger(__name__)


class Router:
    """
    Router class to handle route mappings.

    example usage:
    router = Router()

    router.group("auth")
    router.post("/sign-in", AuthController.sign_in)
    router.post("/sign-up", AuthController.sign_up)

    router.dispatch(lambda_event)
    """
    def __init__(self, silent: bool = False, api_version: str = "auto"):
        self.routes = {}
        self._group = ""
        self._silent = silent
        self._api_version = api_version

    def add_route(self, method: str, path: str, handler):
        if not callable(handler):
            raise TypeError("Handler must be a callable.")

        if self._group:
            path = f"/{self._group}{path}"
        self.routes[method, path] = handler

    def dispatch(self, event: dict):
        request = Request(event, api_version=self._api_version)
        response = Response()
        method = request.method
        path = request.path

        handler = self.routes.get((method, path))
        if not handler:
            if not self._silent:
                logger.warning("Route not found: %s %s", method, path)
            return response.status(404).send("Not Found")

        try:
            return handler(request, response)
        except Exception as exc:
            if not self._silent:
                logger.error("Handler error on %s %s: %s", method, path, exc)
            return response.status(500).json({"error": "Internal Server Error"})

    def group(self, group: str | None):
        self._group = group
        return self

    def get(self, path: str, handler):
        self.add_route("GET", path, handler)

    def post(self, path: str, handler):
        self.add_route("POST", path, handler)

    def put(self, path: str, handler):
        self.add_route("PUT", path, handler)

    def delete(self, path: str, handler):
        self.add_route("DELETE", path, handler)

    def patch(self, path: str, handler):
        self.add_route("PATCH", path, handler)

    def options(self, path: str, handler):
        self.add_route("OPTIONS", path, handler)

    def head(self, path: str, handler):
        self.add_route("HEAD", path, handler)
