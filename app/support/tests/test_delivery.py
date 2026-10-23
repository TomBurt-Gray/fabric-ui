import base64
import json
from collections.abc import Callable
from datetime import timedelta
from io import StringIO
from typing import Self

import pytest
from audit.models import AuditEvent
from django.core.management import call_command
from django.utils import timezone

from support import delivery
from support.delivery import MAX_ATTEMPTS, DeliveryError, GraphSender, attempt_delivery, send_due
from support.models import Delivery
from support.payload import build_email
from support.tests.conftest import FailingSender, RecordingSender

pytestmark = pytest.mark.django_db


@pytest.fixture
def pending(submit: Callable, django_capture_on_commit_callbacks: Callable) -> Delivery:
    """An issue whose first delivery attempt has not run yet."""
    with django_capture_on_commit_callbacks(execute=False):
        submit()
    return Delivery.objects.select_related("issue").get()


def test_send_due_sends_pending_rows(pending: Delivery) -> None:
    sender = RecordingSender()
    assert send_due(sender=sender) == {"due": 1, "sent": 1, "not_sent": 0}
    pending.refresh_from_db()
    assert pending.status == Delivery.Status.SENT and pending.sent_at is not None
    assert sender.sent[0].reference == pending.issue.reference


def test_rows_not_yet_due_are_skipped(pending: Delivery) -> None:
    Delivery.objects.filter(pk=pending.pk).update(
        next_attempt_at=timezone.now() + timedelta(hours=1)
    )
    sender = RecordingSender()
    assert send_due(sender=sender)["due"] == 0
    assert sender.sent == []


def test_sent_rows_are_never_sent_again(pending: Delivery) -> None:
    sender = RecordingSender()
    assert attempt_delivery(pending.pk, sender) is True
    assert attempt_delivery(pending.pk, sender) is False
    assert len(sender.sent) == 1


def test_failure_backs_off(pending: Delivery) -> None:
    before = timezone.now()
    assert attempt_delivery(pending.pk, FailingSender()) is False
    pending.refresh_from_db()
    assert pending.status == Delivery.Status.PENDING
    assert pending.attempts == 1
    assert pending.next_attempt_at >= before + timedelta(minutes=1)
    event = AuditEvent.objects.get(event_type="support.issue_send_failed")
    assert json.loads(event.detail)["fields"]["final"] is False


def test_gives_up_after_max_attempts(pending: Delivery) -> None:
    Delivery.objects.filter(pk=pending.pk).update(attempts=MAX_ATTEMPTS - 1)
    attempt_delivery(pending.pk, FailingSender())
    pending.refresh_from_db()
    assert pending.status == Delivery.Status.FAILED
    event = AuditEvent.objects.filter(event_type="support.issue_send_failed").latest("id")
    assert json.loads(event.detail)["fields"]["final"] is True


def test_send_outbox_command(pending: Delivery, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(delivery, "get_sender", RecordingSender)
    out = StringIO()
    call_command("send_outbox", stdout=out)
    assert out.getvalue().strip() == "due=1 sent=1 not_sent=0"


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Credential:
    def get_token(self, scope: str) -> object:
        assert scope == "https://graph.microsoft.com/.default"
        return type("Token", (), {"token": "test-token"})()


def test_graph_sender_builds_documented_request(pending: Delivery) -> None:
    captured = {}

    def opener(request: object, timeout: int) -> _Response:
        captured["request"] = request
        return _Response(202)

    email = build_email(pending.issue)
    GraphSender(credential=_Credential(), opener=opener).send(email)
    request = captured["request"]
    assert request.method == "POST"
    assert request.full_url == (
        "https://graph.microsoft.com/v1.0/users/support-sender%40example.test/sendMail"
    )
    assert request.get_header("Authorization") == "Bearer test-token"
    body = json.loads(request.data)
    message = body["message"]
    assert message["toRecipients"] == [{"emailAddress": {"address": "support@example.test"}}]
    assert message["internetMessageHeaders"] == [
        {"name": "x-fui-reference", "value": pending.issue.reference}
    ]
    attachment = message["attachments"][0]
    assert attachment["@odata.type"] == "#microsoft.graph.fileAttachment"
    assert json.loads(base64.b64decode(attachment["contentBytes"]))["reference"] == (
        pending.issue.reference
    )
    assert body["saveToSentItems"] is True


def test_graph_sender_rejects_unexpected_status(pending: Delivery) -> None:
    sender = GraphSender(credential=_Credential(), opener=lambda request, timeout: _Response(200))
    with pytest.raises(DeliveryError):
        sender.send(build_email(pending.issue))
