from django.db import models


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
