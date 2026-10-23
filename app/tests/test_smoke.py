"""Scaffold smoke tests: settings load safely and Django system checks pass."""

import importlib
from types import ModuleType

import pytest
from django.conf import settings
from django.core.management import call_command

PROJECT_APPS = ["core", "audit", "support", "catalog", "reports"]


def _reload_settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    for name in ("DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_SECURE_SSL_REDIRECT"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return importlib.reload(importlib.import_module("fabric_ui.settings"))


def test_system_checks_pass() -> None:
    call_command("check")


def test_project_apps_installed() -> None:
    for app in PROJECT_APPS:
        assert app in settings.INSTALLED_APPS


def test_debug_off_and_secure_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_settings(monkeypatch)
    assert module.DEBUG is False
    assert module.SECRET_KEY == ""
    assert module.SESSION_COOKIE_SECURE is True
    assert module.CSRF_COOKIE_SECURE is True
    assert module.SECURE_SSL_REDIRECT is True
    assert module.SECURE_HSTS_SECONDS > 0


def test_dev_secret_key_only_with_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_settings(monkeypatch, DJANGO_DEBUG="true")
    assert module.DEBUG is True
    assert module.SECRET_KEY.startswith("insecure-")
