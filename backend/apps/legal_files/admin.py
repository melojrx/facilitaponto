from django.contrib import admin

from .models import Comprovante


@admin.register(Comprovante)
class ComprovanteAdmin(admin.ModelAdmin):
    list_display = ("registro", "tenant", "timestamp_carimbo", "created_at")
    list_filter = ("tenant",)
    search_fields = ("registro__employee__nome", "registro__employee__pis", "hash_carimbo")
    readonly_fields = (
        "tenant",
        "registro",
        "conteudo_json",
        "timestamp_carimbo",
        "hash_carimbo",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
