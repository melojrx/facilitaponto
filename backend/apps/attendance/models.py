import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.mixins import TenantModelMixin

from .validators import (
    normalize_time_clock_text,
    validate_activation_code,
    validate_latitude,
    validate_longitude,
    validate_radius_meters,
    validate_time_clock_name,
)


class TimeClock(TenantModelMixin, models.Model):
    class TipoRelogio(models.TextChoices):
        APLICATIVO = "APLICATIVO", "Aplicativo"

    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"
        EM_MANUTENCAO = "EM_MANUTENCAO", "Em Manutenção"

    class MetodoAutenticacao(models.TextChoices):
        FACIAL = "FACIAL", "Reconhecimento Facial"

    class Plataforma(models.TextChoices):
        DESCONHECIDA = "DESCONHECIDA", "Desconhecida"
        WEB = "WEB", "Web"
        ANDROID = "ANDROID", "Android"
        IOS = "IOS", "iOS"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=80)
    descricao = models.CharField(max_length=255, blank=True, default="")
    tipo_relogio = models.CharField(
        max_length=20,
        choices=TipoRelogio.choices,
        default=TipoRelogio.APLICATIVO,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ATIVO,
    )
    metodo_autenticacao = models.CharField(
        max_length=20,
        choices=MetodoAutenticacao.choices,
        default=MetodoAutenticacao.FACIAL,
    )
    activation_code = models.CharField(max_length=6, unique=True, db_index=True)
    plataforma = models.CharField(
        max_length=20,
        choices=Plataforma.choices,
        default=Plataforma.DESCONHECIDA,
    )
    current_device = models.OneToOneField(
        "accounts.Device",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="time_clock",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_time_clocks",
    )
    employees = models.ManyToManyField(
        "employees.Employee",
        through="TimeClockEmployeeAssignment",
        related_name="time_clocks",
        blank=True,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome", "created_at"]
        constraints = [
            models.UniqueConstraint(
                Lower("nome"),
                "tenant",
                name="attendance_timeclock_unique_lower_name_per_tenant",
            )
        ]
        verbose_name = "Relógio de Ponto"
        verbose_name_plural = "Relógios de Ponto"

    def __str__(self):
        return self.nome

    @property
    def rep_badge_label(self):
        return "REP-P (Programa/Software)"

    @property
    def colaboradores_total(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {})
        if "employee_assignments" in prefetched:
            return len(prefetched["employee_assignments"])
        return self.employee_assignments.count()

    def clean_fields(self, exclude=None):
        exclude = set(exclude or [])
        if "nome" not in exclude:
            self.nome = validate_time_clock_name(self.nome)
        if "descricao" not in exclude:
            self.descricao = normalize_time_clock_text(self.descricao)
        if "activation_code" not in exclude and self.activation_code:
            self.activation_code = validate_activation_code(self.activation_code)
        return super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        self.nome = validate_time_clock_name(self.nome)

        if self.metodo_autenticacao != self.MetodoAutenticacao.FACIAL:
            raise ValidationError(
                {"metodo_autenticacao": "O relógio suporta apenas Reconhecimento Facial."}
            )

        if self.current_device_id:
            if not self.tenant_id or self.current_device.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"current_device": "Selecione um dispositivo válido da sua empresa."}
                )

        if self.created_by_id:
            if not self.tenant_id or self.created_by.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"created_by": "Usuário criador deve pertencer ao mesmo tenant."}
                )

        if self.nome and self.tenant_id:
            duplicate_qs = TimeClock.all_objects.filter(
                tenant_id=self.tenant_id,
                nome__iexact=self.nome,
            )
            if self.pk:
                duplicate_qs = duplicate_qs.exclude(pk=self.pk)
            if duplicate_qs.exists():
                raise ValidationError({"nome": "Já existe relógio com este nome nesta empresa."})


class TimeClockGeofence(TenantModelMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_clock = models.OneToOneField(
        TimeClock,
        on_delete=models.CASCADE,
        related_name="geofence",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    raio_metros = models.PositiveIntegerField()
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cerca Virtual do Relógio"
        verbose_name_plural = "Cercas Virtuais dos Relógios"

    def __str__(self):
        return f"{self.time_clock.nome} - {self.raio_metros}m"

    def clean(self):
        super().clean()
        validate_latitude(self.latitude)
        validate_longitude(self.longitude)
        validate_radius_meters(self.raio_metros)

        if not self.tenant_id or self.time_clock.tenant_id != self.tenant_id:
            raise ValidationError({"time_clock": "Selecione um relógio válido da sua empresa."})


class TimeClockEmployeeAssignment(TenantModelMixin, models.Model):
    time_clock = models.ForeignKey(
        TimeClock,
        on_delete=models.CASCADE,
        related_name="employee_assignments",
    )
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="time_clock_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee__nome", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "time_clock", "employee"],
                name="attendance_timeclockassignment_unique_employee_per_clock",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "time_clock"]),
            models.Index(fields=["tenant", "employee"]),
        ]
        verbose_name = "Vínculo de Colaborador no Relógio"
        verbose_name_plural = "Vínculos de Colaboradores no Relógio"

    def __str__(self):
        return f"{self.time_clock.nome} -> {self.employee.nome}"

    def clean(self):
        super().clean()

        if not self.tenant_id or self.time_clock.tenant_id != self.tenant_id:
            raise ValidationError({"time_clock": "Selecione um relógio válido da sua empresa."})

        if not self.tenant_id or self.employee.tenant_id != self.tenant_id:
            raise ValidationError(
                {"employee": "Selecione um colaborador válido da sua empresa."}
            )


class AttendanceRecord(TenantModelMixin, models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "E", "Entrada"
        SAIDA = "S", "Saída"
        INICIO_INTERVALO = "II", "Início de Intervalo"
        FIM_INTERVALO = "FI", "Fim de Intervalo"

    class Origem(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.PROTECT,
        related_name="attendance_records",
        db_index=True,
    )
    tipo = models.CharField(max_length=2, choices=Tipo.choices)
    timestamp = models.DateTimeField()
    nsr = models.BigIntegerField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    foto_path = models.CharField(max_length=500)
    foto_hash = models.CharField(max_length=64)
    confianca_biometrica = models.FloatField()
    client_event_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    origem = models.CharField(
        max_length=10,
        choices=Origem.choices,
        default=Origem.ONLINE,
    )
    sincronizado_em = models.DateTimeField(null=True, blank=True)
    justificativa = models.TextField(null=True, blank=True)
    registro_original = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ajustes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "nsr"],
                name="attendance_record_unique_nsr_per_tenant",
            ),
            models.UniqueConstraint(
                fields=["tenant", "client_event_id"],
                condition=Q(client_event_id__isnull=False),
                name="attendance_record_unique_client_event_id_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "employee", "timestamp"]),
        ]
        verbose_name = "Registro de Ponto"
        verbose_name_plural = "Registros de Ponto"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("AttendanceRecord é imutável após criação.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee_id} | {self.tipo} | NSR {self.nsr}"
