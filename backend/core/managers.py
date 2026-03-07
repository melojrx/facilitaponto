"""
TenantManager — filtra queries automaticamente pelo tenant do request.

Uso:
    class MeuModel(TenantModelMixin, models.Model):
        objects = TenantManager()

    # Em uma view com request.tenant injetado pelo TenantMiddleware:
    MeuModel.objects.for_tenant(request.tenant).filter(...)
"""
from django.db import models


class TenantManager(models.Manager):
    """
    Manager que adiciona o método for_tenant() para filtrar por tenant.
    Não filtra por padrão para não quebrar o Django Admin e migrations.
    """

    def for_tenant(self, tenant):
        """Retorna queryset filtrado pelo tenant especificado."""
        return self.get_queryset().filter(tenant=tenant)
