import uuid

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.serializers import TenantTokenObtainPairSerializer


@pytest.mark.django_db
class TestTenantTokenObtainPairSerializer:
    def test_nao_inclui_tenant_id_quando_usuario_nao_tem_tenant(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="user-sem-tenant",
            email="semtenant@example.com",
            password="12345678",
        )

        token = TenantTokenObtainPairSerializer.get_token(user)

        assert "tenant_id" not in token

    def test_inclui_tenant_id_quando_atributo_esta_disponivel(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="user-com-tenant",
            email="comtenant@example.com",
            password="12345678",
        )
        tenant_id = uuid.uuid4()
        user.tenant_id = tenant_id

        token = TenantTokenObtainPairSerializer.get_token(user)

        assert token["tenant_id"] == str(tenant_id)
