"""
TenantMiddleware — resolve o tenant do request e injeta como request.tenant.

Estratégia de resolução (em ordem):
1. JWT: extrai tenant_id do payload do token
2. Subdomínio: tenta resolver por UUID de tenant ou CNPJ (somente quando aplicável)
"""
import uuid

from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.models import Tenant
from core.tenant_context import reset_current_tenant, set_current_tenant


class TenantMiddleware:
    """Injeta tenant no request e no contexto da execução atual."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = self._resolve_tenant(request)
        request.tenant = tenant

        token = set_current_tenant(tenant)
        try:
            return self.get_response(request)
        finally:
            reset_current_tenant(token)

    def _resolve_tenant(self, request):
        """Resolve tenant por JWT e fallback por subdomínio."""
        tenant = self._resolve_tenant_from_jwt(request)
        if tenant is not None:
            return tenant

        return self._resolve_tenant_from_subdomain(request)

    def _resolve_tenant_from_jwt(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        token_str = auth_header.split(" ", 1)[1]
        try:
            token = AccessToken(token_str)
            tenant_id = token.get("tenant_id")
            if not tenant_id:
                return None
            return Tenant.objects.filter(id=tenant_id, ativo=True).first()
        except Exception:
            return None

    def _resolve_tenant_from_subdomain(self, request):
        host = request.META.get("HTTP_HOST", "")
        host_without_port = host.split(":", 1)[0].strip().lower()
        if not host_without_port:
            return None

        host_parts = host_without_port.split(".")
        if len(host_parts) < 3:
            return None

        subdomain = host_parts[0]
        if subdomain in {"www", "api"}:
            return None

        if subdomain.isdigit():
            return Tenant.objects.filter(cnpj=subdomain, ativo=True).first()

        try:
            tenant_uuid = uuid.UUID(subdomain)
        except ValueError:
            return None

        return Tenant.objects.filter(id=tenant_uuid, ativo=True).first()
