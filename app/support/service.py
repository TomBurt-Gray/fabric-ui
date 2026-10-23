"""Raise a support issue: save it, queue its delivery and audit it in one transaction."""

import json
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

from audit.service import audited_action
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from support.config import get_support_config
from support.delivery import attempt_delivery
from support.events import IssueRaised
from support.models import Delivery, SupportIssue


def recent_issue_count(object_id: str) -> int:
    since = timezone.now() - timedelta(hours=1)
    return SupportIssue.objects.filter(requester_object_id=object_id, created_at__gte=since).count()


def filters_from(page_url: str) -> str:
    """The page's query string as JSON: the filters the user was looking at."""
    params = parse_qs(urlsplit(page_url).query, keep_blank_values=True)
    return json.dumps(params, sort_keys=True) if params else ""


def raise_issue(
    request: HttpRequest, fields: dict[str, Any], page_url: str, page_correlation_id: str
) -> SupportIssue:
    """Save the issue and its outbox row with a support.issue_raised audit event.

    If the audit write fails, nothing is saved (D17). Delivery is attempted after commit;
    a delivery failure never affects the saved issue (FR08).
    """
    principal = request.principal
    prefix = get_support_config().reference_prefix
    event = IssueRaised(reference="", type=fields["type"], page=page_url[:512])
    with audited_action(request, event, message="Support issue raised") as draft:
        issue = SupportIssue.objects.create(
            **fields,
            page_url=page_url,
            filters=filters_from(page_url),
            page_correlation_id=page_correlation_id,
            user_agent=request.headers.get("User-Agent", "")[:512],
            requester_object_id=principal.object_id,
            requester_name=principal.display_name,
            requester_email=principal.email,
        )
        issue.reference = f"{prefix}-{issue.created_at:%Y%m%d}-{issue.pk:06d}"
        issue.save(update_fields=["reference"])
        delivery = Delivery.objects.create(issue=issue)
        draft.event = IssueRaised(reference=issue.reference, type=issue.type, page=page_url[:512])
        draft.target = issue.reference
        transaction.on_commit(lambda: attempt_delivery(delivery.pk), robust=True)
    return issue
