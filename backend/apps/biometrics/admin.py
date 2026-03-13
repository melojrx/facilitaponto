from django.contrib import admin

from .models import BiometricInvite, ConsentimentoBiometrico, FacialEmbedding


@admin.register(ConsentimentoBiometrico)
class ConsentimentoBiometricoAdmin(admin.ModelAdmin):
    list_display = ("employee", "aceito", "versao_termo", "ip_origem", "timestamp")
    list_filter = ("aceito", "versao_termo")
    search_fields = ("employee__nome", "employee__cpf", "employee__pis")
    readonly_fields = ("timestamp",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("employee", "employee__tenant")


@admin.register(FacialEmbedding)
class FacialEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("employee", "ativo", "created_at")
    list_filter = ("ativo",)
    search_fields = ("employee__nome", "employee__cpf", "employee__pis")
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("employee", "employee__tenant")


@admin.register(BiometricInvite)
class BiometricInviteAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "channel",
        "status",
        "provider",
        "sent_to",
        "provider_message_id",
        "expires_at",
        "sent_at",
        "used_at",
    )
    list_filter = ("channel", "status", "provider")
    search_fields = ("employee__nome", "employee__cpf", "employee__pis", "sent_to")
    readonly_fields = ("token_hash", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "employee",
            "employee__tenant",
            "created_by",
        )
