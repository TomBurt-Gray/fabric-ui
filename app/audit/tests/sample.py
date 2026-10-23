"""A sample feature for tests: one registered event and views that use the audit API."""

from dataclasses import dataclass

from core.access import any_role
from core.models import UserProfile
from django.http import HttpRequest, HttpResponse
from django.urls import include, path

from audit.events import AuditEventType, Category, register
from audit.service import audited_action


@register
@dataclass(frozen=True)
class SampleChange(AuditEventType):
    event_type = "tests.sample_change"
    category = Category.CONFIG
    item: str
    amount: int


@any_role
def change(request: HttpRequest) -> HttpResponse:
    """Stands in for a business change: creates a row, audited in the same transaction."""
    with audited_action(request, SampleChange(item="widget", amount=3), target="widget") as draft:
        UserProfile.objects.create(object_id="sample-row", last_seen="2026-01-01T00:00:00Z")
        draft.after = {"created": "sample-row"}
    return HttpResponse("changed")


urlpatterns = [
    path("change", change),
    path("", include("core.urls")),
]
