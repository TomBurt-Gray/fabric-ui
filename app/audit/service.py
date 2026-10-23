"""Record audit events. Every feature writes its events through this module.

Use ``audited_action`` around a business change so the change and its audit record commit
together or not at all (D17). Use ``record`` directly only where there is no change to
protect, for example before streaming an export or when denying access.
"""

import contextlib
import ipaddress
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from core.correlation import current_correlation_id
from django.db import DatabaseError, transaction
from django.http import HttpRequest
from django.utils import timezone

from audit.config import get_audit_config
from audit.events import AuditEventType, Outcome, is_registered
from audit.models import AuditEvent

logger = logging.getLogger(__name__)


class AuditUnavailable(Exception):
    """The audit record could not be written, so the action must not go ahead."""


@dataclass
class AuditDraft:
    """Mutable during an ``audited_action`` so the body can fill in results."""

    event: AuditEventType
    target: str = ""
    target_detail: str = ""
    before: Any = None
    after: Any = None
    outcome: Outcome = Outcome.SUCCESS
    message: str = ""


def _json(value: Any) -> str:
    """Deterministic JSON text. Raises TypeError for values that are not JSON safe."""
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _client_ip(request: HttpRequest, header: str) -> str:
    raw = request.headers.get(header, "").split(",")[0].strip() or request.META.get(
        "REMOTE_ADDR", ""
    )
    for candidate in (raw, raw.rsplit(":", 1)[0]):  # "203.0.113.5:51234" carries a port
        try:
            return str(ipaddress.ip_address(candidate.strip("[]")))
        except ValueError:
            continue
    return ""


def build_entry(request: HttpRequest, draft: AuditDraft) -> AuditEvent:
    event = draft.event
    if not is_registered(event):
        raise ValueError(f"{type(event).__name__} is not a registered audit event type")
    config = get_audit_config()
    principal = getattr(request, "principal", None)
    detail = {"fields": event.payload(), "context": config.static_fields}
    return AuditEvent(
        occurred_at=timezone.now(),
        event_type=event.event_type,
        category=event.category,
        outcome=draft.outcome,
        schema_version=event.schema_version,
        source_system=config.source_system,
        environment=config.environment,
        actor_object_id=principal.object_id if principal else "",
        actor_roles=",".join(sorted(principal.roles)) if principal else "",
        target=draft.target[:256],
        target_detail=draft.target_detail[:512],
        before=_json(draft.before),
        after=_json(draft.after),
        detail=_json(detail),
        message=draft.message[:512],
        correlation_id=getattr(request, "correlation_id", "") or current_correlation_id(),
        client_ip=_client_ip(request, config.client_ip_header) if config.capture_network else "",
        user_agent=request.headers.get("User-Agent", "")[:512] if config.capture_network else "",
    )


def record(
    request: HttpRequest,
    event: AuditEventType,
    *,
    target: str = "",
    target_detail: str = "",
    before: Any = None,
    after: Any = None,
    outcome: Outcome = Outcome.SUCCESS,
    message: str = "",
) -> AuditEvent:
    """Write one audit event, joining the caller's transaction if there is one."""
    draft = AuditDraft(event, target, target_detail, before, after, outcome, message)
    entry = build_entry(request, draft)
    try:
        with transaction.atomic():
            entry.save(force_insert=True)
    except DatabaseError as exc:
        logger.exception("Audit write failed for %s", event.event_type)
        raise AuditUnavailable(event.event_type) from exc
    return entry


@contextlib.contextmanager
def audited_action(
    request: HttpRequest, event: AuditEventType, **draft: Any
) -> Iterator[AuditDraft]:
    """Run a business change and its audit record in one transaction.

    The body may update the yielded draft (for example ``draft.after``). If the body raises,
    nothing is recorded. If the audit write fails, the change is rolled back and
    ``AuditUnavailable`` is raised.
    """
    with transaction.atomic():
        pending = AuditDraft(event, **draft)
        yield pending
        record(
            request,
            pending.event,
            target=pending.target,
            target_detail=pending.target_detail,
            before=pending.before,
            after=pending.after,
            outcome=pending.outcome,
            message=pending.message,
        )
