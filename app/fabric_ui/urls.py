"""Root URL configuration. Feature URLs are added from M1 onwards."""

from django.urls import URLPattern, URLResolver

urlpatterns: list[URLPattern | URLResolver] = []
