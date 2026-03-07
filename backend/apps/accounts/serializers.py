"""Serializers de autenticação do app accounts."""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Inclui tenant_id no JWT quando o usuário possui vínculo de tenant.

    Mantém compatibilidade com o User padrão até o DEV-003 implementar
    o model customizado definitivo.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        tenant_id = getattr(user, "tenant_id", None)
        if tenant_id is None:
            tenant = getattr(user, "tenant", None)
            tenant_id = getattr(tenant, "id", None)

        if tenant_id is not None:
            token["tenant_id"] = str(tenant_id)

        return token
