from django.urls import path

from .views import (
    TimeClockActivationApiView,
    TimeClockAssignAllApiView,
    TimeClockAssignedEmployeesApiView,
    TimeClockAssignSelectedApiView,
    TimeClockAvailableEmployeesApiView,
    TimeClockDetailApiView,
    TimeClockGeofenceApiView,
    TimeClockRemoveAllApiView,
    TimeClockRemoveSelectedApiView,
)

urlpatterns = [
    path("ativar/", TimeClockActivationApiView.as_view(), name="time_clock_activate"),
    path("<uuid:time_clock_id>/", TimeClockDetailApiView.as_view(), name="time_clock_detail"),
    path(
        "<uuid:time_clock_id>/cerca-virtual/",
        TimeClockGeofenceApiView.as_view(),
        name="time_clock_geofence",
    ),
    path(
        "<uuid:time_clock_id>/colaboradores/disponiveis/",
        TimeClockAvailableEmployeesApiView.as_view(),
        name="time_clock_available_employees",
    ),
    path(
        "<uuid:time_clock_id>/colaboradores/no-relogio/",
        TimeClockAssignedEmployeesApiView.as_view(),
        name="time_clock_assigned_employees",
    ),
    path(
        "<uuid:time_clock_id>/colaboradores/mover-selecionados/",
        TimeClockAssignSelectedApiView.as_view(),
        name="time_clock_assign_selected",
    ),
    path(
        "<uuid:time_clock_id>/colaboradores/mover-todos/",
        TimeClockAssignAllApiView.as_view(),
        name="time_clock_assign_all",
    ),
    path(
        "<uuid:time_clock_id>/colaboradores/remover-selecionados/",
        TimeClockRemoveSelectedApiView.as_view(),
        name="time_clock_remove_selected",
    ),
    path(
        "<uuid:time_clock_id>/colaboradores/remover-todos/",
        TimeClockRemoveAllApiView.as_view(),
        name="time_clock_remove_all",
    ),
]
