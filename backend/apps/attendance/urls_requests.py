from django.urls import path

from .views import (
    AdjustmentRequestDecisionApiView,
    AdjustmentRequestDetailApiView,
    AdjustmentRequestListApiView,
    RequestSummaryApiView,
)

urlpatterns = [
    path("resumo/", RequestSummaryApiView.as_view(), name="request_summary"),
    path("ajustes/", AdjustmentRequestListApiView.as_view(), name="adjustment_request_list"),
    path("ajustes/<uuid:adjustment_id>/", AdjustmentRequestDetailApiView.as_view(), name="adjustment_request_detail"),
    path(
        "ajustes/<uuid:adjustment_id>/decidir/",
        AdjustmentRequestDecisionApiView.as_view(),
        name="adjustment_request_decide",
    ),
]
