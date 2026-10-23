"""End to end through the middleware: audited changes, failure page, access denied events."""

import json
from collections.abc import Callable

import pytest
from core.models import UserProfile
from core.principal import Role
from django.test import Client

from audit.models import AuditEvent

pytestmark = pytest.mark.django_db

SAMPLE_URLS = "audit.tests.sample"
UNDECLARED_URLS = "core.tests.undeclared_urls"


@pytest.mark.urls(SAMPLE_URLS)
def test_audited_change_succeeds(client: Client, signed_in: Callable) -> None:
    response = client.get("/change", **signed_in(Role.VIEWER))
    assert response.status_code == 200
    assert UserProfile.objects.filter(object_id="sample-row").exists()
    assert AuditEvent.objects.get(event_type="tests.sample_change").target == "widget"


@pytest.mark.urls(SAMPLE_URLS)
def test_audit_failure_shows_try_again_and_changes_nothing(
    client: Client, signed_in: Callable, failing_audit_store: None
) -> None:
    response = client.get("/change?x=1", **signed_in(Role.VIEWER))
    assert response.status_code == 503
    html = response.content.decode()
    assert "Try again" in html
    assert 'href="/change?x=1"' in html
    assert "<html" in html
    assert not UserProfile.objects.filter(object_id="sample-row").exists()


@pytest.mark.urls(SAMPLE_URLS)
def test_audit_failure_htmx_gets_partial(
    client: Client, signed_in: Callable, failing_audit_store: None
) -> None:
    response = client.get("/change", HTTP_HX_REQUEST="true", **signed_in(Role.VIEWER))
    assert response.status_code == 503
    assert "<html" not in response.content.decode()


@pytest.mark.urls(SAMPLE_URLS)
def test_audit_failure_on_post_returns_to_form(
    client: Client, signed_in: Callable, failing_audit_store: None
) -> None:
    response = client.post(
        "/change", HTTP_REFERER="http://testserver/form", **signed_in(Role.VIEWER)
    )
    assert 'href="http://testserver/form"' in response.content.decode()


@pytest.mark.urls(SAMPLE_URLS)
def test_audit_failure_ignores_foreign_referer(
    client: Client, signed_in: Callable, failing_audit_store: None
) -> None:
    response = client.post(
        "/change", HTTP_REFERER="https://evil.example/phish", **signed_in(Role.VIEWER)
    )
    html = response.content.decode()
    assert "evil.example" not in html
    assert 'href="/change"' in html


@pytest.mark.urls(UNDECLARED_URLS)
def test_wrong_role_writes_access_denied(client: Client, signed_in: Callable) -> None:
    assert client.get("/admin-only", **signed_in(Role.VIEWER)).status_code == 403
    row = AuditEvent.objects.get()
    assert row.event_type == "auth.access_denied"
    assert row.outcome == "denied"
    assert row.target == "/admin-only"
    fields = json.loads(row.detail)["fields"]
    assert fields == {"path": "/admin-only", "required_roles": ["admin"], "reason": "missing_role"}


@pytest.mark.urls(UNDECLARED_URLS)
def test_undeclared_view_writes_access_denied(client: Client, signed_in: Callable) -> None:
    client.get("/undeclared", **signed_in(Role.ADMIN))
    assert json.loads(AuditEvent.objects.get().detail)["fields"]["reason"] == "no_access_rule"


def test_unauthenticated_request_is_not_audited(client: Client) -> None:
    assert client.get("/").status_code == 401
    assert not AuditEvent.objects.exists()


@pytest.mark.urls(UNDECLARED_URLS)
def test_denial_stands_when_audit_fails(
    client: Client, signed_in: Callable, failing_audit_store: None
) -> None:
    assert client.get("/admin-only", **signed_in(Role.VIEWER)).status_code == 403
