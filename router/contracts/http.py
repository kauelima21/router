import base64
import json
from urllib.parse import parse_qs


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

        cookie_list = event.get("cookies", [])
        if cookie_list and "cookie" not in self.headers:
            self.headers["cookie"] = "; ".join(cookie_list)

        self.raw_body = event.get("body") or ""
        self.files = {}

        content_type = self.headers.get("content-type", "")

        if "multipart/form-data" in content_type and self.raw_body:
            raw_bytes = self.raw_body
            if event.get("isBase64Encoded"):
                raw_bytes = base64.b64decode(raw_bytes)
            elif isinstance(raw_bytes, str):
                raw_bytes = raw_bytes.encode()

            self.body, self.files = self._parse_multipart(raw_bytes, content_type)
            self.raw_body = ""
        else:
            if event.get("isBase64Encoded") and self.raw_body:
                self.raw_body = base64.b64decode(self.raw_body).decode()

            if not self.raw_body:
                self.body = {}
            elif "application/x-www-form-urlencoded" in content_type:
                parsed = parse_qs(self.raw_body)
                self.body = {k: v[0] for k, v in parsed.items()}
            else:
                try:
                    self.body = json.loads(self.raw_body)
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

    @staticmethod
    def _parse_multipart(raw_bytes: bytes, content_type: str) -> tuple[dict, dict]:
        boundary = None
        for param in content_type.split(";"):
            param = param.strip()
            if param.startswith("boundary="):
                boundary = param[len("boundary="):].strip('"')
                break

        if not boundary:
            return {}, {}

        delimiter = f"--{boundary}".encode()
        parts = raw_bytes.split(delimiter)

        fields = {}
        files = {}

        for part in parts:
            part = part.strip(b"\r\n")
            if not part or part == b"--":
                continue

            if b"\r\n\r\n" not in part:
                continue

            header_section, body = part.split(b"\r\n\r\n", 1)
            if body.endswith(b"\r\n"):
                body = body[:-2]

            headers = {}
            for line in header_section.decode().split("\r\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            disposition = headers.get("content-disposition", "")

            name = None
            filename = None
            for dp in disposition.split(";"):
                dp = dp.strip()
                if dp.startswith("name="):
                    name = dp[len("name="):].strip('"')
                elif dp.startswith("filename="):
                    filename = dp[len("filename="):].strip('"')

            if not name:
                continue

            if filename:
                files[name] = {
                    "filename": filename,
                    "content_type": headers.get("content-type", "application/octet-stream"),
                    "body": body,
                }
            else:
                fields[name] = body.decode()

        return fields, files

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

    def html(self, body: str):
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        self.body = body
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
