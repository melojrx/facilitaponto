from django.core.validators import RegexValidator
from django.db import models

from core.mixins import TenantModelMixin

DIGITS_11_VALIDATOR = RegexValidator(
    regex=r"^\d{11}$",
    message="Este campo deve conter exatamente 11 dígitos numéricos.",
)

SCHEDULE_TYPE_SEMANAL = "SEMANAL"
SCHEDULE_TYPE_12X36 = "12X36"
SCHEDULE_TYPE_FRACIONADA = "FRACIONADA"
SCHEDULE_TYPE_EXTERNA = "EXTERNA"


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


class WorkSchedule(TenantModelMixin, models.Model):
    """Template de jornada de trabalho de uma empresa.

    Representa as configurações de horário esperado que serão vinculadas
    a colaboradores para cálculo de ponto, horas extras e banco de horas.
    """

    class TipoJornada(models.TextChoices):
        SEMANAL = SCHEDULE_TYPE_SEMANAL, "Semanal"
        X12X36 = SCHEDULE_TYPE_12X36, "12x36"
        FRACIONADA = SCHEDULE_TYPE_FRACIONADA, "Fracionada"
        EXTERNA = SCHEDULE_TYPE_EXTERNA, "Externa"

    nome = models.CharField(max_length=80)
    descricao = models.CharField(max_length=255, blank=True, default="")
    tipo = models.CharField(max_length=10, choices=TipoJornada.choices)
    configuracao = models.JSONField(default=dict, blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Jornada de Trabalho"
        verbose_name_plural = "Jornadas de Trabalho"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "nome"],
                condition=models.Q(ativo=True),
                name="employees_workschedule_unique_nome_ativo_per_tenant",
            )
        ]

    def __str__(self):
        return f"{self.nome} ({self.tipo})"
