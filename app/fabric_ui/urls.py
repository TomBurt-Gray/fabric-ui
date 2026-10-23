"""Root URL configuration. Every view must declare access (see core.access)."""

from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
]
