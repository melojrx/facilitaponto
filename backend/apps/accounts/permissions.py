from rest_framework.permissions import BasePermission


class IsTenantMember(BasePermission):
    message = "Usuário não pertence ao tenant do request."

    def has_permission(self, request, view):
        user = request.user
        tenant = getattr(request, "tenant", None)

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        if tenant is None:
            return False

        return str(getattr(user, "tenant_id", "")) == str(tenant.id)


class IsDeviceToken(BasePermission):
    message = "Token de dispositivo inválido para este tenant."

    def has_permission(self, request, view):
        auth = request.auth
        tenant = getattr(request, "tenant", None)

        if auth is None or tenant is None:
            return False

        is_device = bool(auth.get("is_device", False))
        token_tenant_id = auth.get("tenant_id")

        if not is_device or not token_tenant_id:
            return False

        return str(token_tenant_id) == str(tenant.id)
