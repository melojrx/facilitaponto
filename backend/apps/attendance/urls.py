from django.urls import path

from .views import AttendanceComprovanteView, AttendanceRegisterView, AttendanceSyncView

urlpatterns = [
    path("register/", AttendanceRegisterView.as_view(), name="attendance_register"),
    path("sync/", AttendanceSyncView.as_view(), name="attendance_sync"),
    path("<int:record_id>/comprovante/", AttendanceComprovanteView.as_view(), name="attendance_comprovante"),
]
