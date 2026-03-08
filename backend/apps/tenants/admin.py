from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("razao_social", "tipo_pessoa", "documento", "plano", "ativo", "created_at")
    list_filter = ("ativo", "plano", "tipo_pessoa")
    search_fields = ("razao_social", "documento", "cnpj", "nome_fantasia")
    readonly_fields = ("id", "created_at")
    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "id",
                    "tipo_pessoa",
                    "documento",
                    "cnpj",
                    "razao_social",
                    "nome_fantasia",
                )
            },
        ),
        (
            "Contato",
            {"fields": ("email_contato", "telefone_contato", "website", "logo_url")},
        ),
        (
            "Endereço",
            {
                "fields": (
                    "cep",
                    "logradouro",
                    "numero",
                    "complemento",
                    "bairro",
                    "cidade",
                    "estado",
                )
            },
        ),
        (
            "Responsável",
            {"fields": ("responsavel_nome", "responsavel_cpf", "responsavel_cargo")},
        ),
        (
            "Dados adicionais",
            {"fields": ("cno_caepf", "inscricao_estadual", "inscricao_municipal")},
        ),
        ("Configuração", {"fields": ("plano", "registro_inpi", "ativo")}),
        ("Onboarding", {"fields": ("onboarding_step", "onboarding_completed_at")}),
        ("Auditoria", {"fields": ("created_at",)}),
    )
