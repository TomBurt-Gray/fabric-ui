from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.access import any_role, public
from core.branding import get_branding


@any_role
def home(request: HttpRequest) -> HttpResponse:
    roles = sorted(role.value for role in request.principal.roles)
    return render(request, "core/home.html", {"roles": roles})


@public
def healthz(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", content_type="text/plain")


@public
def brand_css(request: HttpRequest) -> HttpResponse:
    """Brand colours as CSS custom properties, so pages need no inline styles."""
    branding = get_branding()
    css = (
        f":root {{ --brand-primary: {branding.primary_colour}; "
        f"--brand-accent: {branding.accent_colour}; }}\n"
    )
    response = HttpResponse(css, content_type="text/css")
    response["Cache-Control"] = "max-age=300"
    return response
