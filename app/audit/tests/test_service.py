import dataclasses
import json
from dataclasses import dataclass

import pytest
from core.models import UserProfile
from django.http import HttpRequest

from audit import service
from audit.config import get_audit_config
from audit.events import AuditEventType, Category, Outcome
from audit.models import AuditEvent
from audit.service import AuditUnavailable, audited_action, record
from audit.tests.sample import SampleChange

pytestmark = pytest.mark.django_db


def test_record_writes_core_fields(audit_request: HttpRequest) -> None:
    record(
        audit_request,
        SampleChange(item="widget", amount=3),
        target="widget",
        target_detail="colour",
        before={"colour": "red"},
        after={"colour": "blue"},
        message="Colour changed",
    )
    row = AuditEvent.objects.get()
    assert row.event_type == "tests.sample_change"
    assert row.category == Category.CONFIG
    assert row.outcome == Outcome.SUCCESS
    assert row.schema_version == 1
    assert (row.source_system, row.environment) == ("fabric-ui", "internal_dev")
    assert row.actor_object_id == "oid-actor"
    assert row.actor_roles == "admin"
    assert (row.target, row.target_detail) == ("widget", "colour")
    assert json.loads(row.before) == {"colour": "red"}
    assert json.loads(row.after) == {"colour": "blue"}
    assert json.loads(row.detail) == {"fields": {"item": "widget", "amount": 3}, "context": {}}
    assert row.correlation_id == "corr-12345678"
    assert row.message == "Colour changed"
    assert row.recorded_at is not None


def test_network_fields_captured_when_enabled(audit_request: HttpRequest) -> None:
    record(audit_request, SampleChange(item="w", amount=1))
    row = AuditEvent.objects.get()
    assert row.client_ip == "203.0.113.5"
    assert row.user_agent == "TestBrowser/1.0"


def test_network_fields_empty_when_disabled(
    audit_request: HttpRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = dataclasses.replace(get_audit_config(), capture_network=False)
    monkeypatch.setattr(service, "get_audit_config", lambda: config)
    record(audit_request, SampleChange(item="w", amount=1))
    row = AuditEvent.objects.get()
    assert (row.client_ip, row.user_agent) == ("", "")


def test_static_fields_added_as_context(
    audit_request: HttpRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = dataclasses.replace(get_audit_config(), static_fields={"business_unit": "Example"})
    monkeypatch.setattr(service, "get_audit_config", lambda: config)
    record(audit_request, SampleChange(item="w", amount=1))
    assert json.loads(AuditEvent.objects.get().detail)["context"] == {"business_unit": "Example"}


def test_unregistered_event_is_refused(audit_request: HttpRequest) -> None:
    @dataclass(frozen=True)
    class Unregistered(AuditEventType):
        event_type = "tests.unregistered"
        category = Category.CONFIG

    with pytest.raises(ValueError):
        record(audit_request, Unregistered())
    assert not AuditEvent.objects.exists()


def test_non_json_payload_is_refused(audit_request: HttpRequest) -> None:
    with pytest.raises(TypeError):
        record(audit_request, SampleChange(item="w", amount=object()))
    assert not AuditEvent.objects.exists()


def test_store_failure_raises_audit_unavailable(
    audit_request: HttpRequest, failing_audit_store: None
) -> None:
    with pytest.raises(AuditUnavailable):
        record(audit_request, SampleChange(item="w", amount=1))


def test_audited_action_commits_change_and_audit(audit_request: HttpRequest) -> None:
    with audited_action(audit_request, SampleChange(item="w", amount=1)) as draft:
        UserProfile.objects.create(object_id="row-1", last_seen="2026-01-01T00:00:00Z")
        draft.after = {"row": "row-1"}
    assert UserProfile.objects.filter(object_id="row-1").exists()
    assert json.loads(AuditEvent.objects.get().after) == {"row": "row-1"}


def test_audit_failure_rolls_back_the_change(
    audit_request: HttpRequest, failing_audit_store: None
) -> None:
    event = SampleChange(item="w", amount=1)
    with pytest.raises(AuditUnavailable), audited_action(audit_request, event):
        UserProfile.objects.create(object_id="row-2", last_seen="2026-01-01T00:00:00Z")
    assert not UserProfile.objects.filter(object_id="row-2").exists()


def test_failed_change_writes_no_audit(audit_request: HttpRequest) -> None:
    event = SampleChange(item="w", amount=1)
    with pytest.raises(RuntimeError), audited_action(audit_request, event):
        UserProfile.objects.create(object_id="row-3", last_seen="2026-01-01T00:00:00Z")
        raise RuntimeError("business rule failed")
    assert not UserProfile.objects.filter(object_id="row-3").exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("203.0.113.5", "203.0.113.5"),
        ("203.0.113.5:443, 10.0.0.1", "203.0.113.5"),
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("not-an-ip", ""),
    ],
)
def test_client_ip_parsing(header: str, expected: str) -> None:
    from django.test import RequestFactory

    request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR=header, REMOTE_ADDR="")
    assert service._client_ip(request, "X-Forwarded-For") == expected
