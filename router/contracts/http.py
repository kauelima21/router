import json


class Request:
    def __init__(self, event: dict, api_version: str = "auto") -> None:
        self.request_context = event["requestContext"]

        if api_version == "auto":
            api_version = "v2" if "routeKey" in event else "v1"

        if api_version == "v1":
            self._parse_v1(event)
        else:
            self._parse_v2(event)

        self.query = event.get("queryStringParameters") or {}
        self.params = event.get("pathParameters") or {}
        self.headers = event["headers"]

        self.raw_body = event.get("body") or ""
        try:
            self.body = json.loads(self.raw_body) if self.raw_body else {}
        except (json.JSONDecodeError, TypeError):
            self.body = {}

    def _parse_v1(self, event: dict) -> None:
        self.method = event["httpMethod"]
        self.path = event["resource"]
        self.raw_path = event["path"]
        self.authenticated_user = (
            self.request_context.get("authorizer", {}).get("claims", {})
        )

    def _parse_v2(self, event: dict) -> None:
        route_key = event["routeKey"]
        self.raw_path = event["rawPath"]
        self.path = route_key.split(" ")[1] if " " in route_key else self.raw_path
        self.method = self.request_context["http"]["method"]
        self.authenticated_user = (
            self.request_context.get("authorizer", {}).get("jwt", {}).get("claims", {})
        )

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "path": self.path,
            "queryStringParameters": self.query,
            "headers": self.headers,
            "body": self.body,
            "isBase64Encoded": False,
            "rawPath": self.raw_path,
        }

    def __str__(self):
        return str(self.to_dict())


class Response:
    def __init__(self) -> None:
        self.status_code = 200
        self.headers = {}
        self.cookies = []
        self.body = None

    def status(self, status_code: int):
        self.status_code = status_code
        return self

    def send(self, body: str):
        self.body = body
        if not self.headers.get("Content-Type"):
            self.headers["Content-Type"] = "text/plain"
        return self._finalize()

    def json(self, body: dict | list):
        from router.utils import json_dumps

        self.headers["Content-Type"] = "application/json"
        self.body = json_dumps(body)
        return self._finalize()

    def set(self, key: str, value: str):
        self.headers[key] = str(value)
        return self

    def cookie(self, cookie: str):
        self.cookies.append(cookie)
        return self

    def _finalize(self) -> dict:
        response = {
            "statusCode": self.status_code,
            "headers": dict(self.headers),
            "isBase64Encoded": False,
            "cookies": self.cookies,
        }

        if self.body is not None:
            response["body"] = self.body

        return response

    def to_dict(self) -> dict:
        return {
            "statusCode": self.status_code,
            "headers": dict(self.headers),
            "cookies": self.cookies,
            "body": self.body,
            "isBase64Encoded": False,
        }

    def __str__(self):
        return str(self.to_dict())
