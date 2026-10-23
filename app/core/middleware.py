"""Authentication, authorisation and security header middleware."""

import logging
from collections.abc import Callable

from audit.events import AccessDenied, Outcome
from audit.service import AuditUnavailable, record
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
            return self._deny(request, required=(), reason="no_access_rule")
        if not request.principal.has_any(rule.roles):
            return self._deny(request, required=sorted(rule.roles), reason="missing_role")
        return None

    def _deny(self, request: HttpRequest, required: list | tuple, reason: str) -> HttpResponse:
        """Audit the denial; the denial stands even if the audit write fails."""
        event = AccessDenied(path=request.path[:512], required_roles=tuple(required), reason=reason)
        try:
            record(
                request,
                event,
                target=request.path,
                outcome=Outcome.DENIED,
                message="Access denied",
            )
        except AuditUnavailable:
            logger.error("Access to %s denied but the audit write failed", request.path)
        return forbidden(request)


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response
