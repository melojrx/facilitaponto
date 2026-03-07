from django.contrib import admin

from .models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "tenant", "tipo", "timestamp", "nsr", "origem", "client_event_id")
    list_filter = ("tenant", "tipo", "origem")
    search_fields = ("employee__nome", "employee__cpf", "employee__pis", "foto_hash")
    readonly_fields = (
        "tenant",
        "employee",
        "tipo",
        "timestamp",
        "nsr",
        "latitude",
        "longitude",
        "foto_path",
        "foto_hash",
        "confianca_biometrica",
        "client_event_id",
        "origem",
        "sincronizado_em",
        "justificativa",
        "registro_original",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
