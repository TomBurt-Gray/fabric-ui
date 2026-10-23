from django.urls import path

from core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("brand.css", views.brand_css, name="brand_css"),
]
