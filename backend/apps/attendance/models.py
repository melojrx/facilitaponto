from django.core.exceptions import ValidationError
from django.db import models

from core.mixins import TenantModelMixin


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
            )
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
