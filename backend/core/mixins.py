"""
TenantModelMixin — adiciona FK para Tenant e managers padrão.

`objects`: manager com isolamento automático por tenant.
`all_objects`: manager sem filtro para usos administrativos/controlados.
"""
from django.db import models

from core.managers import TenantManager


class TenantModelMixin(models.Model):
    """
    Mixin abstrato que adiciona o campo tenant a qualquer model.
    Todos os models que contêm dados de uma empresa DEVEM herdar este mixin.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    objects = TenantManager()
    all_objects = TenantManager(scoped=False)

    class Meta:
        abstract = True
