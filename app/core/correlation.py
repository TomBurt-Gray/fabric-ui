"""Correlation IDs: one per request, reused from the caller when well formed."""

import logging
import re
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

HEADER = "X-Correlation-ID"
# Strict format so caller supplied values cannot inject into logs.
_VALID = re.compile(r"[A-Za-z0-9._-]{8,128}")
_current: ContextVar[str] = ContextVar("correlation_id", default="-")


def current_correlation_id() -> str:
    return _current.get()


class CorrelationIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(HEADER, "")
        correlation_id = incoming if _VALID.fullmatch(incoming) else uuid.uuid4().hex
        request.correlation_id = correlation_id
        token = _current.set(correlation_id)
        try:
            response = self.get_response(request)
        finally:
            _current.reset(token)
        response[HEADER] = correlation_id
        return response


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _current.get()
        return True
