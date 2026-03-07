from django.core.validators import RegexValidator
from django.db import models

from core.mixins import TenantModelMixin

DIGITS_11_VALIDATOR = RegexValidator(
    regex=r"^\d{11}$",
    message="Este campo deve conter exatamente 11 dígitos numéricos.",
)


class Employee(TenantModelMixin, models.Model):
    nome = models.CharField(max_length=255)
    cpf = models.CharField(max_length=11, validators=[DIGITS_11_VALIDATOR])
    pis = models.CharField(max_length=11, validators=[DIGITS_11_VALIDATOR])
    email = models.EmailField(blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "cpf"],
                name="employees_employee_unique_cpf_per_tenant",
            )
        ]
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"

    def __str__(self):
        return f"{self.nome} ({self.cpf})"


class NSRSequence(TenantModelMixin, models.Model):
    ultimo_nsr = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"],
                name="employees_nsrsequence_unique_tenant",
            )
        ]
        verbose_name = "Sequência NSR"
        verbose_name_plural = "Sequências NSR"

    def __str__(self):
        return f"{self.tenant_id} -> {self.ultimo_nsr}"
