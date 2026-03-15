from django.urls import path

from .views import (
    TreatmentPointAutoAdjustApiView,
    TreatmentPointAdjustmentDecisionApiView,
    TreatmentPointDayAdjustmentApiView,
    TreatmentPointEmployeeListApiView,
    TreatmentPointMirrorApiView,
)

urlpatterns = [
    path("colaboradores/", TreatmentPointEmployeeListApiView.as_view(), name="treatment_point_employee_list"),
    path("espelho/<int:employee_id>/", TreatmentPointMirrorApiView.as_view(), name="treatment_point_mirror"),
    path(
        "espelho/<int:employee_id>/dias/<str:date>/ajustes/",
        TreatmentPointDayAdjustmentApiView.as_view(),
        name="treatment_point_day_adjustment",
    ),
    path(
        "espelho/<int:employee_id>/ajuste-automatico/",
        TreatmentPointAutoAdjustApiView.as_view(),
        name="treatment_point_auto_adjust",
    ),
    path(
        "espelho/<int:employee_id>/ajustes/<uuid:adjustment_id>/decisao/",
        TreatmentPointAdjustmentDecisionApiView.as_view(),
        name="treatment_point_adjustment_decision",
    ),
]
