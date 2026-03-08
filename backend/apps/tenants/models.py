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

    class TipoPessoa(models.TextChoices):
        PJ = "PJ", "Pessoa Jurídica"
        PF = "PF", "Pessoa Física"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cnpj = models.CharField(max_length=14, unique=True, null=True, blank=True)
    tipo_pessoa = models.CharField(
        max_length=2,
        choices=TipoPessoa.choices,
        default=TipoPessoa.PJ,
    )
    documento = models.CharField(max_length=14, unique=True, null=True, blank=True)
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255, blank=True)
    email_contato = models.EmailField(blank=True, default="")
    telefone_contato = models.CharField(max_length=20, blank=True, default="")
    cep = models.CharField(max_length=8, blank=True, default="")
    logradouro = models.CharField(max_length=255, blank=True, default="")
    numero = models.CharField(max_length=20, blank=True, default="")
    complemento = models.CharField(max_length=255, blank=True, default="")
    bairro = models.CharField(max_length=120, blank=True, default="")
    cidade = models.CharField(max_length=120, blank=True, default="")
    estado = models.CharField(max_length=2, blank=True, default="")
    responsavel_nome = models.CharField(max_length=255, blank=True, default="")
    responsavel_cpf = models.CharField(max_length=11, blank=True, default="")
    responsavel_cargo = models.CharField(max_length=120, blank=True, default="")
    logo_url = models.URLField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    cno_caepf = models.CharField(max_length=20, blank=True, default="")
    inscricao_estadual = models.CharField(max_length=30, blank=True, default="")
    inscricao_municipal = models.CharField(max_length=30, blank=True, default="")
    onboarding_step = models.PositiveSmallIntegerField(default=1)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
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
        return f"{self.razao_social} ({self.documento or self.cnpj or 'sem-doc'})"
