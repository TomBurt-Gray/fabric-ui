from collections.abc import Callable, Iterator

import pytest
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver

from core.access import access_rule, require_roles
from core.principal import Role

pytestmark = pytest.mark.django_db

UNDECLARED_URLS = "core.tests.undeclared_urls"


def _patterns(resolver: URLResolver) -> Iterator[URLPattern]:
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _patterns(pattern)
        else:
            yield pattern


def test_every_view_declares_access() -> None:
    undeclared = [str(p.pattern) for p in _patterns(get_resolver()) if not access_rule(p.callback)]
    assert undeclared == []


def test_unauthenticated_request_is_rejected(client: Client) -> None:
    assert client.get("/").status_code == 401


def test_any_role_can_open_home(client: Client, signed_in: Callable) -> None:
    for role in Role:
        assert client.get("/", **signed_in(role)).status_code == 200


def test_principal_without_roles_is_forbidden(client: Client, signed_in: Callable) -> None:
    response = client.get("/", **signed_in())
    assert response.status_code == 403
    assert b"Access denied" in response.content


def test_public_endpoints_need_no_principal(client: Client) -> None:
    assert client.get("/healthz").content == b"ok"
    assert client.get("/brand.css").status_code == 200


@pytest.mark.urls(UNDECLARED_URLS)
def test_undeclared_view_is_denied(client: Client, signed_in: Callable) -> None:
    assert client.get("/undeclared", **signed_in(*Role)).status_code == 403


@pytest.mark.urls(UNDECLARED_URLS)
def test_wrong_role_is_forbidden(client: Client, signed_in: Callable) -> None:
    assert client.get("/admin-only", **signed_in(Role.VIEWER)).status_code == 403
    assert client.get("/admin-only", **signed_in(Role.ADMIN)).status_code == 200


@pytest.mark.urls(UNDECLARED_URLS)
def test_restricted_view_rejects_unauthenticated(client: Client) -> None:
    assert client.get("/admin-only").status_code == 401


def test_require_roles_needs_a_role() -> None:
    with pytest.raises(ValueError):
        require_roles()


def test_security_headers(client: Client, signed_in: Callable) -> None:
    response = client.get("/", **signed_in(Role.VIEWER))
    assert "default-src 'self'" in response["Content-Security-Policy"]
    assert response["X-Frame-Options"] == "DENY"
