"""
TenantManager — aplica isolamento por tenant automaticamente.

- `objects` (scoped=True): filtra dados pelo tenant ativo em contexto.
- `all_objects` (scoped=False): acesso explícito sem filtro para usos administrativos.
"""
from django.db import models

from core.tenant_context import get_current_tenant


class TenantManager(models.Manager):
    """
    Manager tenant-aware.

    Quando scoped=True, o queryset padrão só retorna dados do tenant atual.
    Se não houver tenant no contexto, retorna queryset vazio por segurança.
    """

    def __init__(self, *args, scoped=True, **kwargs):
        self.scoped = scoped
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.scoped:
            return queryset

        tenant = get_current_tenant()
        if tenant is None:
            return queryset.none()

        return queryset.filter(tenant=tenant)

    def for_tenant(self, tenant):
        """Retorna queryset filtrado por tenant explicitamente."""
        queryset = super().get_queryset()
        if tenant is None:
            return queryset.none()
        return queryset.filter(tenant=tenant)

    def unscoped(self):
        """Acesso explícito sem filtro tenant-aware."""
        return super().get_queryset()
