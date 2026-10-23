"""Local development only: inject a synthetic Easy Auth principal.

Refuses to load unless DEBUG is on and the app is not running on App Service, so a
misconfigured deployment fails to start instead of trusting a fake identity.
"""

import os
from collections.abc import Callable

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse

from core.principal import encode_principal


def assert_dev_auth_allowed(debug: bool) -> None:
    if not debug:
        raise ImproperlyConfigured("The dev auth shim requires DEBUG to be on.")
    if os.environ.get("WEBSITE_SITE_NAME"):
        raise ImproperlyConfigured("The dev auth shim must never run on App Service.")


class DevPrincipalMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        assert_dev_auth_allowed(settings.DEBUG)
        self.get_response = get_response
        self.header = encode_principal(
            object_id=settings.DEV_AUTH_OBJECT_ID,
            name=settings.DEV_AUTH_NAME,
            email=settings.DEV_AUTH_EMAIL,
            roles=settings.DEV_AUTH_ROLES,
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.META["HTTP_X_MS_CLIENT_PRINCIPAL"] = self.header
        request.__dict__.pop("headers", None)  # Drop any cached copy built before the injection.
        return self.get_response(request)
