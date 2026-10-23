from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme

from audit.service import AuditUnavailable


def _retry_url(request: HttpRequest) -> str:
    """Same URL for safe methods; otherwise back to the page that submitted the form."""
    if request.method in ("GET", "HEAD"):
        return request.get_full_path()
    referer = request.headers.get("Referer", "")
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return referer
    return request.path


class AuditFailureMiddleware:
    """Turn an audit write failure into a clear 503 with a Try again link (D17)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        if not isinstance(exception, AuditUnavailable):
            return None
        partial = request.headers.get("HX-Request") == "true"
        template = "audit/unavailable_partial.html" if partial else "audit/unavailable.html"
        return render(request, template, {"retry_url": _retry_url(request)}, status=503)
