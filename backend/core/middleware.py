"""
TenantMiddleware — resolve o tenant do request e injeta como request.tenant.

Estratégia de resolução (em ordem):
1. JWT: extrai tenant_id do payload do token
2. Usuário autenticado (vínculo direto/heurística sem persistência)
3. Subdomínio: tenta resolver por UUID de tenant ou CNPJ (somente quando aplicável)
"""
from core.tenant_context import reset_current_tenant, set_current_tenant
from core.tenant_resolution import resolve_tenant_for_request


class TenantMiddleware:
    """Injeta tenant no request e no contexto da execução atual."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = resolve_tenant_for_request(request)
        request.tenant = tenant

        token = set_current_tenant(tenant)
        try:
            return self.get_response(request)
        finally:
            reset_current_tenant(token)
