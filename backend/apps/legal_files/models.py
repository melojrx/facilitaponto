from django.db import models

from core.mixins import TenantModelMixin


class Comprovante(TenantModelMixin, models.Model):
    registro = models.OneToOneField(
        "attendance.AttendanceRecord",
        on_delete=models.CASCADE,
        related_name="comprovante",
    )
    conteudo_json = models.JSONField()
    timestamp_carimbo = models.DateTimeField()
    hash_carimbo = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Comprovante"
        verbose_name_plural = "Comprovantes"

    def __str__(self):
        return f"NSR {self.registro.nsr} - {self.registro.employee_id}"
