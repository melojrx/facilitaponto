from django.urls import path

from .views import ActiveEmployeesView

urlpatterns = [
    path("active/", ActiveEmployeesView.as_view(), name="employees_active"),
]
