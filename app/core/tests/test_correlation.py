import logging
import re

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory

from core.correlation import HEADER, CorrelationIdFilter, CorrelationIdMiddleware


def test_valid_incoming_id_is_reused(client: Client) -> None:
    response = client.get("/healthz", HTTP_X_CORRELATION_ID="abc-123.XYZ_9")
    assert response[HEADER] == "abc-123.XYZ_9"


@pytest.mark.parametrize("incoming", ["", "short", "bad id\ninjected", "x" * 129])
def test_invalid_incoming_id_is_replaced(client: Client, incoming: str) -> None:
    response = client.get("/healthz", HTTP_X_CORRELATION_ID=incoming)
    assert re.fullmatch(r"[0-9a-f]{32}", response[HEADER])


def test_log_records_carry_the_id(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.correlation")

    def view(request: HttpRequest) -> HttpResponse:
        logger.warning("inside request")
        return HttpResponse()

    caplog.handler.addFilter(CorrelationIdFilter())
    request = RequestFactory().get("/", HTTP_X_CORRELATION_ID="abcdef123")
    CorrelationIdMiddleware(view)(request)
    record = next(r for r in caplog.records if r.getMessage() == "inside request")
    assert record.correlation_id == "abcdef123"
