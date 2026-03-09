"""Roteamento web inicial (P0)."""

from django.urls import path

from .web_views import (
    company_view,
    company_edit_view,
    create_company_view,
    create_journey_view,
    delete_journey_view,
    edit_journey_view,
    journey_list_view,
    landing_view,
    login_view,
    logout_view,
    module_placeholder_view,
    painel_view,
    profile_view,
    signup_view,
)

app_name = "web"

urlpatterns = [
    path("", landing_view, name="landing"),
    path("cadastro/", signup_view, name="signup"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("painel/", painel_view, name="painel"),
    path("painel/perfil/", profile_view, name="profile"),
    path("painel/empresa/", company_view, name="company"),
    path("painel/empresa/editar/", company_edit_view, name="company_edit"),
    path("painel/empresa/nova/", create_company_view, name="company_create"),
    path("painel/jornadas/nova/", create_journey_view, name="journey_create"),
    path("painel/jornadas/<int:journey_id>/editar/", edit_journey_view, name="journey_edit"),
    path("painel/jornadas/<int:journey_id>/excluir/", delete_journey_view, name="journey_delete"),
    path("painel/jornadas/", journey_list_view, name="jornadas"),
    path("painel/colaboradores/", module_placeholder_view, {"module_key": "colaboradores"}, name="colaboradores"),
    path("painel/relogio-digital/", module_placeholder_view, {"module_key": "relogio_digital"}, name="relogio_digital"),
    path(
        "painel/tratamento-ponto/",
        module_placeholder_view,
        {"module_key": "tratamento_ponto"},
        name="tratamento_ponto",
    ),
    path("painel/relatorios/", module_placeholder_view, {"module_key": "relatorios"}, name="relatorios"),
    path("painel/solicitacoes/", module_placeholder_view, {"module_key": "solicitacoes"}, name="solicitacoes"),
    path("painel/configuracoes/", module_placeholder_view, {"module_key": "configuracoes"}, name="configuracoes"),
]
