"""The support_issue.v1 contract and the email built from it."""

import json
from dataclasses import dataclass
from datetime import UTC

from audit.config import get_audit_config
from core.branding import get_branding
from django.urls import reverse

from support.config import get_support_config
from support.models import IMPACT_FLAGS, IssueType, SupportIssue

SCHEMA_ID = "support_issue.v1"


@dataclass(frozen=True)
class OutgoingEmail:
    reference: str
    sender: str
    recipient: str
    subject: str
    body: str
    attachment_name: str
    attachment: bytes


def issue_payload(issue: SupportIssue) -> dict:
    """Reference level summary only: no description, page, filters or data (D22)."""
    audit = get_audit_config()
    support = get_support_config()
    return {
        "schema": SCHEMA_ID,
        "reference": issue.reference,
        "environment": audit.environment,
        "source_system": audit.source_system,
        "type": issue.type,
        "subject": issue.subject,
        "requester": {"name": issue.requester_name, "email": issue.requester_email},
        "impact": {flag: getattr(issue, flag) for flag in IMPACT_FLAGS},
        "created_utc": issue.created_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "correlation_id": issue.page_correlation_id,
        "issue_url": support.app_base_url + reverse("support:issue_detail", args=[issue.reference]),
    }


def build_email(issue: SupportIssue) -> OutgoingEmail:
    support = get_support_config()
    payload = issue_payload(issue)
    type_label = IssueType(issue.type).label
    body = support.render_body(
        {
            "app_name": get_branding().app_name,
            "environment": payload["environment"],
            "reference": issue.reference,
            "type_label": type_label,
            "subject": issue.subject,
            "requester_name": issue.requester_name,
            "requester_email": issue.requester_email,
            "created_utc": payload["created_utc"],
            "impact_summary": ", ".join(issue.impact_labels()) or "None reported",
            "issue_url": payload["issue_url"],
        }
    )
    return OutgoingEmail(
        reference=issue.reference,
        sender=support.sender_mailbox,
        recipient=support.recipient_mailbox,
        subject=f"{issue.reference} {type_label}: {issue.subject}",
        body=body,
        attachment_name=f"{issue.reference}.{SCHEMA_ID}.json",
        attachment=json.dumps(payload, indent=2, sort_keys=True).encode(),
    )
