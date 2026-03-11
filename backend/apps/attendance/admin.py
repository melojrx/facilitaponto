from django.contrib import admin

from .models import AttendanceRecord, TimeClock, TimeClockEmployeeAssignment, TimeClockGeofence


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


@admin.register(TimeClock)
class TimeClockAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "tenant",
        "status",
        "tipo_relogio",
        "metodo_autenticacao",
        "activation_code",
        "last_synced_at",
    )
    list_filter = ("tenant", "status", "tipo_relogio", "metodo_autenticacao")
    search_fields = ("nome", "descricao", "activation_code")
    readonly_fields = ("activation_code", "created_at", "updated_at")


@admin.register(TimeClockGeofence)
class TimeClockGeofenceAdmin(admin.ModelAdmin):
    list_display = ("time_clock", "tenant", "latitude", "longitude", "raio_metros", "ativo")
    list_filter = ("tenant", "ativo")
    search_fields = ("time_clock__nome",)


@admin.register(TimeClockEmployeeAssignment)
class TimeClockEmployeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ("time_clock", "employee", "tenant", "created_at")
    list_filter = ("tenant",)
    search_fields = ("time_clock__nome", "employee__nome", "employee__cpf")
