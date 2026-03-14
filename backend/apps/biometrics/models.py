import hashlib

from django.db import models
from django.utils import timezone

from core.mixins import TenantModelMixin


class ConsentimentoBiometrico(models.Model):
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="consentimentos_biometricos",
        db_index=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    aceito = models.BooleanField(default=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    versao_termo = models.CharField(max_length=20)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Consentimento Biométrico"
        verbose_name_plural = "Consentimentos Biométricos"

    def __str__(self):
        status = "aceito" if self.aceito else "recusado"
        return f"{self.employee_id} - {status} - {self.timestamp.isoformat()}"


class FacialEmbedding(models.Model):
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="facial_embeddings",
        db_index=True,
    )
    embedding_data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Embedding Facial"
        verbose_name_plural = "Embeddings Faciais"

    def __str__(self):
        status = "ativo" if self.ativo else "inativo"
        return f"{self.employee_id} - {status}"


class BiometricInvite(TenantModelMixin, models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falhou"
        USED = "used", "Utilizado"
        EXPIRED = "expired", "Expirado"
        REVOKED = "revoked", "Revogado"

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="biometric_invites",
        db_index=True,
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="biometric_invites_created",
        null=True,
        blank=True,
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WHATSAPP)
    provider = models.CharField(max_length=30, blank=True, default="")
    sent_to = models.CharField(max_length=20)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    last_error = models.CharField(max_length=255, blank=True, default="")
    provider_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Convite Biométrico"
        verbose_name_plural = "Convites Biométricos"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "employee", "token_hash"],
                name="biometrics_biometricinvite_unique_employee_token_per_tenant",
            )
        ]

    def __str__(self):
        return f"{self.employee_id} -> {self.channel} -> {self.status}"

    @staticmethod
    def build_token_hash(raw_token):
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_active(self):
        return (
            self.status in {self.Status.PENDING, self.Status.SENT}
            and self.used_at is None
            and not self.is_expired
        )
