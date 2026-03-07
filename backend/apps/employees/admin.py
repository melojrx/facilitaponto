from django.contrib import admin

from .models import Employee, NSRSequence


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf", "pis", "tenant", "ativo", "created_at")
    list_filter = ("tenant", "ativo")
    search_fields = ("nome", "cpf", "pis")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return Employee.all_objects.select_related("tenant")


@admin.register(NSRSequence)
class NSRSequenceAdmin(admin.ModelAdmin):
    list_display = ("tenant", "ultimo_nsr", "updated_at")
    readonly_fields = ("updated_at",)

    def get_queryset(self, request):
        return NSRSequence.all_objects.select_related("tenant")
