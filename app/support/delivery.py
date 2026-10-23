"""Deliver support issues from the outbox.

Each issue has a Delivery row created in the same transaction as the issue. A first attempt
runs straight after commit; ``manage.py send_outbox`` retries due rows with backoff. Rows are
locked while sending so concurrent runners never send the same issue twice. The transport is
pluggable (D24): email now, a tracker API later.
"""

import base64
import json
import logging
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import timedelta
from typing import Protocol

from audit.events import Outcome
from audit.service import record_system
from django.db import connection, transaction
from django.utils import timezone

from support.config import get_support_config
from support.events import IssueSendFailed, IssueSent
from support.models import Delivery
from support.payload import OutgoingEmail, build_email

logger = logging.getLogger(__name__)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
BACKOFF_MINUTES = (1, 5, 15, 60)
MAX_ATTEMPTS = 10


class DeliveryError(Exception):
    pass


class Sender(Protocol):
    def send(self, email: OutgoingEmail) -> None: ...


class ConsoleSender:
    """Local development: log the email instead of sending it."""

    def send(self, email: OutgoingEmail) -> None:
        logger.info(
            "Support email (console delivery)\nTo: %s\nFrom: %s\nSubject: %s\n\n%s\nAttachment %s:\n%s",
            email.recipient,
            email.sender,
            email.subject,
            email.body,
            email.attachment_name,
            email.attachment.decode(),
        )


class GraphSender:
    """Microsoft Graph sendMail from the configured mailbox with the app's managed identity.

    Mail.Send must be scoped to the sending mailbox only, never tenant wide (architecture).
    """

    def __init__(self, credential: object | None = None, opener: Callable | None = None) -> None:
        self._credential = credential
        self._opener = opener or urllib.request.urlopen

    def _token(self) -> str:
        if self._credential is None:
            from azure.identity import DefaultAzureCredential

            self._credential = DefaultAzureCredential()
        return self._credential.get_token(GRAPH_SCOPE).token

    def request_body(self, email: OutgoingEmail) -> dict:
        return {
            "message": {
                "subject": email.subject,
                "body": {"contentType": "Text", "content": email.body},
                "toRecipients": [{"emailAddress": {"address": email.recipient}}],
                "internetMessageHeaders": [{"name": "x-fui-reference", "value": email.reference}],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": email.attachment_name,
                        "contentType": "application/json",
                        "contentBytes": base64.b64encode(email.attachment).decode(),
                    }
                ],
            },
            "saveToSentItems": True,
        }

    def send(self, email: OutgoingEmail) -> None:
        request = urllib.request.Request(
            GRAPH_SEND_URL.format(sender=urllib.parse.quote(email.sender)),
            data=json.dumps(self.request_body(email)).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
            },
        )
        with self._opener(request, timeout=30) as response:
            # 202 means accepted for delivery, not delivered (Microsoft Learn, user-sendmail).
            if response.status != 202:
                raise DeliveryError(f"Graph sendMail returned {response.status}")


def get_sender() -> Sender:
    return GraphSender() if get_support_config().delivery == "graph" else ConsoleSender()


def _next_attempt(attempts: int) -> timedelta:
    return timedelta(minutes=BACKOFF_MINUTES[min(attempts, len(BACKOFF_MINUTES)) - 1])


def _locked_due(delivery_id: int) -> Delivery | None:
    queryset = Delivery.objects.select_related("issue")
    if connection.features.has_select_for_update_skip_locked:
        queryset = queryset.select_for_update(skip_locked=True)
    return queryset.filter(
        pk=delivery_id, status=Delivery.Status.PENDING, next_attempt_at__lte=timezone.now()
    ).first()


def attempt_delivery(delivery_id: int, sender: Sender | None = None) -> bool:
    """Try to send one due delivery. Returns True if it was sent."""
    with transaction.atomic():
        delivery = _locked_due(delivery_id)
        if delivery is None:
            return False  # Not due, already sent, or another runner holds it.
        delivery.attempts += 1
        reference = delivery.issue.reference
        try:
            (sender or get_sender()).send(build_email(delivery.issue))
        # Deliberately broad: any transport failure (network, auth, HTTP) must leave the issue
        # pending in the outbox rather than escape and lose the attempt record.
        except Exception as exc:  # noqa: BLE001
            final = delivery.attempts >= MAX_ATTEMPTS
            delivery.status = Delivery.Status.FAILED if final else Delivery.Status.PENDING
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:1000]
            delivery.next_attempt_at = timezone.now() + _next_attempt(delivery.attempts)
            delivery.save()
            log = logger.error if final else logger.warning
            log("Delivery of %s failed (attempt %s): %s", reference, delivery.attempts, exc)
            record_system(
                IssueSendFailed(
                    reference=reference,
                    channel=delivery.channel,
                    attempt=delivery.attempts,
                    error=delivery.last_error[:200],
                    final=final,
                ),
                target=reference,
                outcome=Outcome.FAILED,
            )
            return False
        delivery.status = Delivery.Status.SENT
        delivery.sent_at = timezone.now()
        delivery.last_error = ""
        delivery.save()
        record_system(
            IssueSent(reference=reference, channel=delivery.channel, attempt=delivery.attempts),
            target=reference,
        )
        return True


def send_due(limit: int = 50, sender: Sender | None = None) -> dict[str, int]:
    """Attempt every due pending delivery. Used by ``manage.py send_outbox``."""
    due = list(
        Delivery.objects.filter(
            status=Delivery.Status.PENDING, next_attempt_at__lte=timezone.now()
        ).values_list("pk", flat=True)[:limit]
    )
    sent = sum(attempt_delivery(pk, sender) for pk in due)
    return {"due": len(due), "sent": sent, "not_sent": len(due) - sent}
