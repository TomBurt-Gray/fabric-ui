from collections.abc import Callable

import pytest
from audit.models import AuditEvent
from core.principal import Role
from django.test import Client

from support.models import SupportIssue

pytestmark = pytest.mark.django_db


@pytest.fixture
def issue(submit: Callable, django_capture_on_commit_callbacks: Callable) -> SupportIssue:
    with django_capture_on_commit_callbacks(execute=False):
        submit()
    return SupportIssue.objects.get()


@pytest.mark.parametrize("path", ["/support/issues", "/support/issues/FUI-20260101-000001"])
def test_only_support_role_sees_issues(client: Client, signed_in: Callable, path: str) -> None:
    for role in (Role.VIEWER, Role.REPORT_USER, Role.ADMIN):
        assert client.get(path, **signed_in(role)).status_code == 403


def test_support_list_shows_issue(client: Client, signed_in: Callable, issue: SupportIssue) -> None:
    html = client.get("/support/issues", **signed_in(Role.SUPPORT)).content.decode()
    assert issue.reference in html
    assert "Export button does nothing" in html


def test_support_detail_is_audited(
    client: Client, signed_in: Callable, issue: SupportIssue
) -> None:
    response = client.get(f"/support/issues/{issue.reference}", **signed_in(Role.SUPPORT))
    html = response.content.decode()
    assert response.status_code == 200
    assert issue.description in html
    assert "Open trades, click export." in html
    event = AuditEvent.objects.get(event_type="support.issue_viewed")
    assert event.target == issue.reference


def test_unknown_reference_is_404(client: Client, signed_in: Callable) -> None:
    response = client.get("/support/issues/FUI-20260101-999999", **signed_in(Role.SUPPORT))
    assert response.status_code == 404


def test_detail_not_shown_if_view_audit_fails(
    client: Client, signed_in: Callable, issue: SupportIssue, failing_audit_store: None
) -> None:
    response = client.get(f"/support/issues/{issue.reference}", **signed_in(Role.SUPPORT))
    assert response.status_code == 503
    assert issue.description not in response.content.decode()


def test_nav_link_for_support_role_only(client: Client, signed_in: Callable) -> None:
    assert "Support issues" in client.get("/", **signed_in(Role.SUPPORT)).content.decode()
    assert "Support issues" not in client.get("/", **signed_in(Role.VIEWER)).content.decode()
