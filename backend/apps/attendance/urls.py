from django.urls import path

from .views import AttendanceRegisterView

urlpatterns = [
    path("register/", AttendanceRegisterView.as_view(), name="attendance_register"),
]
