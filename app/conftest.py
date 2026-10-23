from collections.abc import Callable
from typing import Any

import pytest
from core.principal import Role, encode_principal
from django.db import DatabaseError

TEST_OBJECT_ID = "00000000-0000-0000-0000-0000000000aa"


@pytest.fixture(autouse=True)
def _test_settings(settings: Any) -> None:
    # No collectstatic in unit tests, and the test client uses plain HTTP.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.SECURE_SSL_REDIRECT = False


@pytest.fixture
def signed_in() -> Callable[..., dict[str, str]]:
    """Request kwargs carrying a synthetic Easy Auth principal with the given roles."""

    def make(*roles: Role, object_id: str = TEST_OBJECT_ID, name: str = "Test User") -> dict:
        header = encode_principal(
            object_id=object_id,
            name=name,
            email="test.user@example.test",
            roles=[role.value for role in roles],
        )
        return {"HTTP_X_MS_CLIENT_PRINCIPAL": header}

    return make


@pytest.fixture
def failing_audit_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every audit insert fail as if the database were unavailable."""
    from audit.models import AuditEvent

    def fail(self: AuditEvent, *args: object, **kwargs: object) -> None:
        raise DatabaseError("audit store unavailable")

    monkeypatch.setattr(AuditEvent, "save", fail)
