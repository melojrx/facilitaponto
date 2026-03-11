from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from core.mixins import TenantModelMixin

from .journey_config import normalize_config_for_tipo
from .validators import (
    normalize_optional_email,
    normalize_optional_phone,
    normalize_optional_text,
    validate_employee_cpf,
    validate_employee_name,
    validate_employee_pis,
    validate_not_future,
)

DIGITS_11_VALIDATOR = RegexValidator(
    regex=r"^\d{11}$",
    message="Este campo deve conter exatamente 11 dígitos numéricos.",
)

SCHEDULE_TYPE_SEMANAL = "SEMANAL"
SCHEDULE_TYPE_12X36 = "12X36"
SCHEDULE_TYPE_FRACIONADA = "FRACIONADA"
SCHEDULE_TYPE_EXTERNA = "EXTERNA"


class Employee(TenantModelMixin, models.Model):
    class BiometricStatus(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONSENTIMENTO = "CONSENTIMENTO", "Consentimento Pendente"
        CADASTRADA = "CADASTRADA", "Cadastro Facial Concluido"

    nome = models.CharField(max_length=255)
    cpf = models.CharField(max_length=11, validators=[DIGITS_11_VALIDATOR])
    pis = models.CharField(max_length=11, validators=[DIGITS_11_VALIDATOR])
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=11, blank=True, default="")
    data_nascimento = models.DateField(null=True, blank=True)
    funcao = models.CharField(max_length=120, blank=True, default="")
    departamento = models.CharField(max_length=120, blank=True, default="")
    data_admissao = models.DateField(null=True, blank=True)
    matricula_interna = models.CharField(max_length=50, blank=True, default="")
    work_schedule = models.ForeignKey(
        "employees.WorkSchedule",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "cpf"],
                name="employees_employee_unique_cpf_per_tenant",
            ),
            models.UniqueConstraint(
                fields=["tenant", "matricula_interna"],
                condition=~models.Q(matricula_interna=""),
                name="employees_employee_unique_matricula_per_tenant",
            ),
        ]
        verbose_name = "Funcionário"
        verbose_name_plural = "Funcionários"

    def __str__(self):
        return f"{self.nome} ({self.cpf})"

    def _prefetched_related_list(self, related_name):
        prefetched = getattr(self, "_prefetched_objects_cache", {})
        if related_name in prefetched:
            return list(prefetched[related_name])
        return list(getattr(self, related_name).all())

    def biometric_snapshot(self):
        embeddings = self._prefetched_related_list("facial_embeddings")
        consents = self._prefetched_related_list("consentimentos_biometricos")

        active_embedding = next((embedding for embedding in embeddings if embedding.ativo), None)
        latest_consent = consents[0] if consents else None

        if active_embedding:
            return {
                "status": self.BiometricStatus.CADASTRADA,
                "label": self.BiometricStatus.CADASTRADA.label,
                "detail": (
                    f"Cadastro facial concluido em {timezone.localtime(active_embedding.created_at).strftime('%d/%m/%Y %H:%M')}."
                ),
                "latest_consent_at": latest_consent.timestamp if latest_consent else None,
                "latest_embedding_at": active_embedding.created_at,
                "has_active_consent": bool(latest_consent and latest_consent.aceito),
                "has_active_embedding": True,
            }

        if latest_consent and latest_consent.aceito:
            return {
                "status": self.BiometricStatus.CONSENTIMENTO,
                "label": self.BiometricStatus.CONSENTIMENTO.label,
                "detail": (
                    f"Consentimento registrado em {timezone.localtime(latest_consent.timestamp).strftime('%d/%m/%Y %H:%M')}. Enroll facial pendente."
                ),
                "latest_consent_at": latest_consent.timestamp,
                "latest_embedding_at": None,
                "has_active_consent": True,
                "has_active_embedding": False,
            }

        if latest_consent and not latest_consent.aceito:
            return {
                "status": self.BiometricStatus.PENDENTE,
                "label": self.BiometricStatus.PENDENTE.label,
                "detail": (
                    f"Ultimo consentimento biometrico recusado em {timezone.localtime(latest_consent.timestamp).strftime('%d/%m/%Y %H:%M')}."
                ),
                "latest_consent_at": latest_consent.timestamp,
                "latest_embedding_at": None,
                "has_active_consent": False,
                "has_active_embedding": False,
            }

        return {
            "status": self.BiometricStatus.PENDENTE,
            "label": self.BiometricStatus.PENDENTE.label,
            "detail": "Sem consentimento biometrico registrado.",
            "latest_consent_at": None,
            "latest_embedding_at": None,
            "has_active_consent": False,
            "has_active_embedding": False,
        }

    @property
    def biometric_status(self):
        return self.biometric_snapshot()["status"]

    @property
    def biometric_status_label(self):
        return self.biometric_snapshot()["label"]

    def clean_fields(self, exclude=None):
        exclude = set(exclude or [])
        if "nome" not in exclude:
            self.nome = normalize_optional_text(self.nome)
        if "cpf" not in exclude and self.cpf:
            self.cpf = validate_employee_cpf(self.cpf)
        if "pis" not in exclude and self.pis:
            self.pis = validate_employee_pis(self.pis)
        if "email" not in exclude:
            self.email = normalize_optional_email(self.email)
        if "telefone" not in exclude:
            self.telefone = normalize_optional_phone(self.telefone)
        if "funcao" not in exclude:
            self.funcao = normalize_optional_text(self.funcao)
        if "departamento" not in exclude:
            self.departamento = normalize_optional_text(self.departamento)
        if "matricula_interna" not in exclude:
            self.matricula_interna = normalize_optional_text(self.matricula_interna)
        return super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        self.nome = validate_employee_name(self.nome)
        validate_not_future(self.data_nascimento)
        validate_not_future(self.data_admissao)

        if self.work_schedule_id:
            if not self.tenant_id or self.work_schedule.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"work_schedule": "Selecione uma jornada valida da sua empresa."}
                )
        elif self.ativo:
            raise ValidationError(
                {"work_schedule": "Informe uma jornada de trabalho para o colaborador."}
            )

        if self.cpf and self.tenant_id:
            duplicate_cpf_qs = Employee.all_objects.filter(
                tenant_id=self.tenant_id,
                cpf=self.cpf,
            )
            if self.pk:
                duplicate_cpf_qs = duplicate_cpf_qs.exclude(pk=self.pk)
            if duplicate_cpf_qs.exists():
                raise ValidationError({"cpf": "Ja existe colaborador com este CPF nesta empresa."})

        if self.matricula_interna and self.tenant_id:
            duplicate_qs = Employee.all_objects.filter(
                tenant_id=self.tenant_id,
                matricula_interna=self.matricula_interna,
            )
            if self.pk:
                duplicate_qs = duplicate_qs.exclude(pk=self.pk)
            if duplicate_qs.exists():
                raise ValidationError(
                    {"matricula_interna": "Ja existe colaborador com esta matricula nesta empresa."}
                )


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

    def clean(self):
        super().clean()
        self.configuracao = normalize_config_for_tipo(self.tipo, self.configuracao)
