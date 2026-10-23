from collections.abc import Callable

import pytest
from core.principal import Role
from django.http import HttpResponse
from django.test import Client

from support.payload import OutgoingEmail

VALID_FORM = {
    "type": "defect",
    "subject": "Export button does nothing",
    "description": "Clicking export on the trades table has no effect.",
    "steps_to_reproduce": "Open trades, click export.",
    "deadline_at_risk": "on",
    "page": "/tables/gold.fact_trades?trade_date=2026-10-01&sort=-notional",
    "page_correlation_id": "page-corr-123456",
}


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []

    def send(self, email: OutgoingEmail) -> None:
        self.sent.append(email)


class FailingSender:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, email: OutgoingEmail) -> None:
        self.calls += 1
        raise ConnectionError("mail service unreachable")


@pytest.fixture
def submit(client: Client, signed_in: Callable) -> Callable[..., HttpResponse]:
    """POST the issue form as an HTMX request from a signed in viewer."""
    headers = signed_in(Role.VIEWER)

    def post(**overrides: str) -> HttpResponse:
        return client.post(
            "/support/new", {**VALID_FORM, **overrides}, HTTP_HX_REQUEST="true", **headers
        )

    return post
