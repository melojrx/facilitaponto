"""Roteamento web inicial (P0)."""

from django.urls import path

from .web_views import (
    capture_collaborator_biometric_view,
    collaborator_list_view,
    company_edit_view,
    company_view,
    create_collaborator_view,
    create_company_view,
    create_journey_view,
    create_time_clock_view,
    delete_journey_view,
    edit_collaborator_view,
    edit_journey_view,
    edit_time_clock_view,
    journey_list_view,
    landing_view,
    login_view,
    logout_view,
    module_placeholder_view,
    painel_view,
    profile_view,
    signup_view,
    time_clock_detail_view,
    time_clock_list_view,
    toggle_collaborator_status_view,
    toggle_time_clock_status_view,
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
    path("painel/colaboradores/novo/", create_collaborator_view, name="colaborador_create"),
    path("painel/colaboradores/<int:employee_id>/editar/", edit_collaborator_view, name="colaborador_edit"),
    path(
        "painel/colaboradores/<int:employee_id>/biometria/capturar/",
        capture_collaborator_biometric_view,
        name="colaborador_biometria_capture",
    ),
    path(
        "painel/colaboradores/<int:employee_id>/status/",
        toggle_collaborator_status_view,
        name="colaborador_status_toggle",
    ),
    path("painel/colaboradores/", collaborator_list_view, name="colaboradores"),
    path("painel/relogios/novo/", create_time_clock_view, name="relogio_create"),
    path("painel/relogios/<uuid:time_clock_id>/", time_clock_detail_view, name="relogio_detail"),
    path(
        "painel/relogios/<uuid:time_clock_id>/editar/",
        edit_time_clock_view,
        name="relogio_edit",
    ),
    path(
        "painel/relogios/<uuid:time_clock_id>/status/",
        toggle_time_clock_status_view,
        name="relogio_status_toggle",
    ),
    path("painel/relogios/", time_clock_list_view, name="relogio_digital"),
    path("painel/relogio-digital/", time_clock_list_view, name="relogio_digital_legacy"),
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
