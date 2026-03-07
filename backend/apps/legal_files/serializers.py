from rest_framework import serializers

from .models import Comprovante


class ComprovanteSerializer(serializers.ModelSerializer):
    registro_id = serializers.IntegerField(read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Comprovante
        fields = (
            "id",
            "tenant_id",
            "registro_id",
            "conteudo_json",
            "timestamp_carimbo",
            "hash_carimbo",
            "created_at",
        )
        read_only_fields = fields
