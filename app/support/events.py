"""Audit events for support issues."""

from dataclasses import dataclass

from audit.events import AuditEventType, Category, register


@register
@dataclass(frozen=True)
class IssueRaised(AuditEventType):
    event_type = "support.issue_raised"
    category = Category.SUPPORT
    reference: str
    type: str
    page: str


@register
@dataclass(frozen=True)
class IssueSent(AuditEventType):
    event_type = "support.issue_sent"
    category = Category.SUPPORT
    reference: str
    channel: str
    attempt: int


@register
@dataclass(frozen=True)
class IssueSendFailed(AuditEventType):
    event_type = "support.issue_send_failed"
    category = Category.SUPPORT
    reference: str
    channel: str
    attempt: int
    error: str
    final: bool


@register
@dataclass(frozen=True)
class IssueViewed(AuditEventType):
    """A support user opened an issue's full detail."""

    event_type = "support.issue_viewed"
    category = Category.SUPPORT
    reference: str
