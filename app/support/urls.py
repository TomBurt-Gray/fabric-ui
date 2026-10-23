from django.urls import path

from support import views

app_name = "support"

urlpatterns = [
    path("new", views.new_issue, name="new_issue"),
    path("issues", views.issue_list, name="issue_list"),
    path("issues/<str:reference>", views.issue_detail, name="issue_detail"),
]
