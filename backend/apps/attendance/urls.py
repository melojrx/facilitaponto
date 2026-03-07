from django.urls import path

from .views import AttendanceComprovanteView, AttendanceRegisterView

urlpatterns = [
    path("register/", AttendanceRegisterView.as_view(), name="attendance_register"),
    path("<int:record_id>/comprovante/", AttendanceComprovanteView.as_view(), name="attendance_comprovante"),
]
