"""Roteamento web inicial (P0)."""

from django.urls import path

from .web_views import landing_view, login_view, logout_view, painel_view, signup_view

app_name = "web"

urlpatterns = [
    path("", landing_view, name="landing"),
    path("cadastro/", signup_view, name="signup"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("painel/", painel_view, name="painel"),
]
