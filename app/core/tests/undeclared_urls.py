"""URLconf for tests: a view with no access declaration and an admin only view.

The real core URLs are included because the layout links to them.
"""

from django.http import HttpRequest, HttpResponse
from django.urls import include, path

from core.access import require_roles
from core.principal import Role


def undeclared(request: HttpRequest) -> HttpResponse:
    return HttpResponse("should never be served")


@require_roles(Role.ADMIN)
def admin_only(request: HttpRequest) -> HttpResponse:
    return HttpResponse("admin content")


urlpatterns = [
    path("undeclared", undeclared),
    path("admin-only", admin_only),
    path("", include("core.urls")),
]
