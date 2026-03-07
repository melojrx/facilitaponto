from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("razao_social", "cnpj", "plano", "ativo", "created_at")
    list_filter = ("ativo", "plano")
    search_fields = ("razao_social", "cnpj", "nome_fantasia")
    readonly_fields = ("id", "created_at")
    fieldsets = (
        ("Identificação", {"fields": ("id", "cnpj", "razao_social", "nome_fantasia")}),
        ("Configuração", {"fields": ("plano", "registro_inpi", "ativo")}),
        ("Auditoria", {"fields": ("created_at",)}),
    )
