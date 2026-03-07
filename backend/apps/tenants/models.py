import uuid

from django.db import models


class Tenant(models.Model):
    """
    Representa uma empresa contratante do SaaS.
    Todos os dados do sistema são isolados por tenant (row-level isolation).
    """

    class Plano(models.TextChoices):
        BASICO = "basico", "Básico"
        PROFISSIONAL = "profissional", "Profissional"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cnpj = models.CharField(max_length=14, unique=True)
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    registro_inpi = models.CharField(
        max_length=50,
        blank=True,
        help_text="Número de registro do software no INPI — obrigatório para AFD/AEJ",
    )
    plano = models.CharField(max_length=20, choices=Plano.choices, default=Plano.BASICO)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["razao_social"]

    def __str__(self) -> str:
        return f"{self.razao_social} ({self.cnpj})"
