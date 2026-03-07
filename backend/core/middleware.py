"""
TenantMiddleware — resolve o tenant do request e injeta como request.tenant.

Estratégia de resolução (em ordem):
1. JWT: extrai tenant_id do payload do token (fluxo principal — app mobile e painel web)
2. Subdomínio: extrai tenant via host (ex: empresa.ponto.app) — opcional para v2

O middleware garante que request.tenant está sempre disponível nas views autenticadas.
Views que não requerem autenticação (ex: login) terão request.tenant = None.
"""
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.models import Tenant


class TenantMiddleware:
    """
    Injeta o tenant no request baseado no JWT do header Authorization.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = self._resolve_tenant(request)
        return self.get_response(request)

    def _resolve_tenant(self, request):
        """Tenta extrair o tenant_id do JWT e retorna o Tenant correspondente."""
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
