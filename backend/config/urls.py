"""
URL configuration principal do projeto.
Cada app registra suas próprias urls via include().
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
    path("", include("apps.accounts.web_urls")),
]
