"""Authentication, authorisation and security header middleware."""

import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.access import access_rule
from core.principal import parse_principal
from core.profiles import record_profile

logger = logging.getLogger(__name__)

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; object-src 'none'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)


def forbidden(request: HttpRequest) -> HttpResponse:
    return render(request, "403.html", status=403)


class EasyAuthMiddleware:
    """Attach ``request.principal`` and enforce each view's access rule (default deny)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.principal = parse_principal(request.headers)
        if request.principal is not None:
            record_profile(request.principal)
        return self.get_response(request)

    def process_view(
        self, request: HttpRequest, view_func: Callable, view_args: tuple, view_kwargs: dict
    ) -> HttpResponse | None:
        rule = access_rule(view_func)
        if rule is not None and rule.public:
            return None
        if request.principal is None:
            return HttpResponse("Authentication required.", status=401, content_type="text/plain")
        if rule is None:
            logger.error("View %s declares no access rule; denied", view_func.__qualname__)
            return forbidden(request)
        if not request.principal.has_any(rule.roles):
            return forbidden(request)
        return None


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response
