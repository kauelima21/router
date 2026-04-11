import pytest

from router import Router


def make_event(
    method="GET",
    path="/test",
    body=None,
    query=None,
    params=None,
    headers=None,
    route_key=None,
    claims=None,
):
    event = {
        "routeKey": route_key or f"{method} {path}",
        "rawPath": path,
        "headers": headers or {"content-type": "application/json"},
        "requestContext": {
            "http": {"method": method},
        },
    }

    if query is not None:
        event["queryStringParameters"] = query

    if params is not None:
        event["pathParameters"] = params

    if body is not None:
        event["body"] = body

    if claims:
        event["requestContext"]["authorizer"] = {"jwt": {"claims": claims}}

    return event


def make_v1_event(
    method="GET",
    path="/test",
    resource=None,
    body=None,
    query=None,
    params=None,
    headers=None,
    claims=None,
):
    event = {
        "httpMethod": method,
        "resource": resource or path,
        "path": path,
        "headers": headers or {"content-type": "application/json"},
        "requestContext": {},
    }

    if query is not None:
        event["queryStringParameters"] = query

    if params is not None:
        event["pathParameters"] = params

    if body is not None:
        event["body"] = body

    if claims:
        event["requestContext"]["authorizer"] = {"claims": claims}

    return event


@pytest.fixture
def event_factory():
    return make_event


@pytest.fixture
def v1_event_factory():
    return make_v1_event


@pytest.fixture
def router():
    return Router()
