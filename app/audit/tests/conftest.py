import pytest
from core.principal import Principal, Role
from django.http import HttpRequest
from django.test import RequestFactory

ACTOR = Principal("oid-actor", "Ada Example", "ada@example.test", frozenset({Role.ADMIN}), "aad")


@pytest.fixture
def audit_request() -> HttpRequest:
    request = RequestFactory().get(
        "/somewhere",
        HTTP_USER_AGENT="TestBrowser/1.0",
        HTTP_X_FORWARDED_FOR="203.0.113.5:51234, 10.0.0.1",
    )
    request.principal = ACTOR
    request.correlation_id = "corr-12345678"
    return request
