from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Device, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "tenant", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active", "is_superuser")
    search_fields = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Vínculo", {"fields": ("tenant", "role")}),
        (
            "Permissões",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Auditoria", {"fields": ("last_login", "created_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "tenant",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    readonly_fields = ("last_login", "created_at")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("tenant", "device_id", "nome", "ativo", "last_seen_at", "created_at")
    list_filter = ("tenant", "ativo")
    search_fields = ("device_id", "nome")
    readonly_fields = ("id", "created_at", "updated_at", "last_seen_at")
