import importlib
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from core.dev_auth import DevPrincipalMiddleware
from core.principal import Role, parse_principal


def _respond_with_roles(request: HttpRequest) -> HttpResponse:
    principal = parse_principal(request.headers)
    return HttpResponse(",".join(sorted(principal.roles)) if principal else "none")


def test_refuses_to_load_without_debug(settings: Any) -> None:
    settings.DEBUG = False
    with pytest.raises(ImproperlyConfigured):
        DevPrincipalMiddleware(_respond_with_roles)


def test_refuses_to_load_on_app_service(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.DEBUG = True
    monkeypatch.setenv("WEBSITE_SITE_NAME", "some-app")
    with pytest.raises(ImproperlyConfigured):
        DevPrincipalMiddleware(_respond_with_roles)


def test_settings_refuse_dev_auth_without_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_DEBUG", raising=False)
    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")
    with pytest.raises(ImproperlyConfigured):
        importlib.reload(importlib.import_module("fabric_ui.settings"))


def test_injects_synthetic_principal_in_local_dev(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings.DEBUG = True
    settings.DEV_AUTH_ROLES = ["viewer", "support"]
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    middleware = DevPrincipalMiddleware(_respond_with_roles)
    request = RequestFactory().get("/")
    _ = request.headers  # Cache headers first, as earlier middleware would.
    response = middleware(request)
    assert response.content.decode() == f"{Role.SUPPORT},{Role.VIEWER}"
