"""
TenantModelMixin — adiciona FK para Tenant em qualquer model.

Uso:
    class Employee(TenantModelMixin, models.Model):
        nome = models.CharField(max_length=255)
        objects = TenantManager()
"""
from django.db import models


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

    class Meta:
        abstract = True
