import dataclasses
import json
import re
from collections.abc import Callable

import pytest
from audit.models import AuditEvent
from core.principal import Role
from django.test import Client

from support import delivery, views
from support.config import get_support_config
from support.models import Delivery, SupportIssue
from support.tests.conftest import FailingSender

pytestmark = pytest.mark.django_db

REFERENCE = re.compile(r"FUI-\d{8}-\d{6}")


def test_form_loads_as_partial_for_htmx(client: Client, signed_in: Callable) -> None:
    response = client.get(
        "/support/new?from=/somewhere&cid=abc12345",
        HTTP_HX_REQUEST="true",
        **signed_in(Role.VIEWER),
    )
    html = response.content.decode()
    assert response.status_code == 200
    assert "What kind of issue is it?" in html
    assert "<html" not in html
    assert 'value="/somewhere"' in html


def test_form_has_full_page_fallback(client: Client, signed_in: Callable) -> None:
    html = client.get("/support/new", **signed_in(Role.VIEWER)).content.decode()
    assert "<html" in html and "Report an issue" in html


def test_issue_is_saved_queued_and_audited(
    submit: Callable, django_capture_on_commit_callbacks: Callable
) -> None:
    with django_capture_on_commit_callbacks(execute=False):
        response = submit()
    assert response.status_code == 201
    issue = SupportIssue.objects.get()
    assert REFERENCE.fullmatch(issue.reference)
    assert issue.reference in response.content.decode()
    assert issue.type == "defect"
    assert issue.deadline_at_risk is True and issue.processing_stopped is False
    assert (issue.requester_name, issue.requester_email) == ("Test User", "test.user@example.test")
    assert issue.page_url == "/tables/gold.fact_trades?trade_date=2026-10-01&sort=-notional"
    assert json.loads(issue.filters) == {"sort": ["-notional"], "trade_date": ["2026-10-01"]}
    assert issue.page_correlation_id == "page-corr-123456"
    assert Delivery.objects.get().status == Delivery.Status.PENDING
    event = AuditEvent.objects.get(event_type="support.issue_raised")
    assert event.target == issue.reference
    assert json.loads(event.detail)["fields"]["reference"] == issue.reference


def test_delivery_runs_after_commit(
    submit: Callable, django_capture_on_commit_callbacks: Callable
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        submit()
    assert Delivery.objects.get().status == Delivery.Status.SENT
    assert AuditEvent.objects.filter(
        event_type="support.issue_sent", actor_object_id="system"
    ).exists()


def test_delivery_failure_never_loses_the_issue(
    submit: Callable,
    django_capture_on_commit_callbacks: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(delivery, "get_sender", FailingSender)
    with django_capture_on_commit_callbacks(execute=True):
        response = submit()
    assert response.status_code == 201
    assert SupportIssue.objects.exists()
    row = Delivery.objects.get()
    assert (row.status, row.attempts) == (Delivery.Status.PENDING, 1)
    assert "ConnectionError" in row.last_error
    assert AuditEvent.objects.filter(event_type="support.issue_send_failed").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [("subject", ""), ("description", ""), ("type", "problem"), ("type", "change")],
)
def test_invalid_form_is_rejected(submit: Callable, field: str, value: str) -> None:
    response = submit(**{field: value})
    assert response.status_code == 422
    assert not SupportIssue.objects.exists()


@pytest.mark.parametrize(
    "page", ["//evil.example/phish", "https://evil.example/x", "javascript:alert(1)", "no-slash"]
)
def test_foreign_page_urls_are_dropped(submit: Callable, page: str) -> None:
    submit(page=page)
    assert SupportIssue.objects.get().page_url == ""


def test_bad_correlation_id_is_dropped(submit: Callable) -> None:
    submit(page_correlation_id="bad id\ninjected")
    assert SupportIssue.objects.get().page_correlation_id == ""


def test_rate_limit(submit: Callable, monkeypatch: pytest.MonkeyPatch) -> None:
    config = dataclasses.replace(get_support_config(), rate_limit_per_hour=1)
    monkeypatch.setattr(views, "get_support_config", lambda: config)
    assert submit().status_code == 201
    response = submit()
    assert response.status_code == 429
    assert "Please try again later" in response.content.decode()
    assert SupportIssue.objects.count() == 1


def test_audit_failure_saves_nothing(submit: Callable, failing_audit_store: None) -> None:
    response = submit()
    assert response.status_code == 503
    assert "Try again" in response.content.decode()
    assert not SupportIssue.objects.exists()
    assert not Delivery.objects.exists()


def test_report_link_on_every_page(client: Client, signed_in: Callable) -> None:
    html = client.get("/?x=1", **signed_in(Role.VIEWER)).content.decode()
    assert 'hx-get="/support/new?from=/%3Fx%3D1&amp;cid=' in html
    assert 'id="issue-dialog"' in html
