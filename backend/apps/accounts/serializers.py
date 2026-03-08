"""Serializers de autenticação do app accounts."""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Inclui claims de tenant e role no JWT de usuário."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        if getattr(user, "tenant_id", None):
            token["tenant_id"] = str(user.tenant_id)

        token["role"] = getattr(user, "role", "")
        token["is_device"] = False

        return token


class DeviceRegisterSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=100)
    nome = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate_device_id(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("device_id é obrigatório.")
        return normalized


class PublicCepLookupSerializer(serializers.Serializer):
    cep = serializers.CharField(max_length=9)

    def validate_cep(self, value):
        digits = "".join(ch for ch in (value or "") if ch.isdigit())
        if len(digits) != 8:
            raise serializers.ValidationError("Informe um CEP válido com 8 dígitos.")
        return digits
