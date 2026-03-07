from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Device, User
from apps.accounts.permissions import IsDeviceToken, IsTenantMember
from apps.accounts.serializers import TenantTokenObtainPairSerializer
from apps.tenants.models import Tenant


@pytest.fixture
def tenant_a(db):
    return Tenant.objects.create(
        cnpj="11111111000111",
        razao_social="Tenant A",
        plano=Tenant.Plano.BASICO,
    )


@pytest.fixture
def tenant_b(db):
    return Tenant.objects.create(
        cnpj="22222222000122",
        razao_social="Tenant B",
        plano=Tenant.Plano.PROFISSIONAL,
    )


@pytest.fixture
def user_a(db, tenant_a):
    return User.objects.create_user(
        email="admin@tenanta.com",
        password="12345678",
        tenant=tenant_a,
        role=User.Role.ADMIN,
    )


@pytest.fixture
def user_b(db, tenant_b):
    return User.objects.create_user(
        email="viewer@tenantb.com",
        password="12345678",
        tenant=tenant_b,
        role=User.Role.VIEWER,
    )


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_com_email_e_tenant(self, tenant_a):
        user = User.objects.create_user(
            email="gestor@tenanta.com",
            password="12345678",
            tenant=tenant_a,
            role=User.Role.GESTOR,
        )

        assert user.email == "gestor@tenanta.com"
        assert user.tenant == tenant_a
        assert user.role == User.Role.GESTOR
        assert user.is_staff is False

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email="root@ponto.com",
            password="12345678",
        )

        assert superuser.is_superuser is True
        assert superuser.is_staff is True


@pytest.mark.django_db
class TestTenantTokenObtainPairSerializer:
    def test_inclui_tenant_id_e_role_no_token(self, user_a):
        token = TenantTokenObtainPairSerializer.get_token(user_a)

        assert token["tenant_id"] == str(user_a.tenant_id)
        assert token["role"] == user_a.role
        assert token["is_device"] is False

    def test_nao_inclui_tenant_id_para_usuario_sem_tenant(self):
        user = User.objects.create_superuser(email="root2@ponto.com", password="12345678")

        token = TenantTokenObtainPairSerializer.get_token(user)

        assert "tenant_id" not in token


@pytest.mark.django_db
class TestPermissions:
    def test_is_tenant_member_permitemesmo_tenant(self, user_a, tenant_a):
        request = SimpleNamespace(user=user_a, tenant=tenant_a)

        assert IsTenantMember().has_permission(request, view=None) is True

    def test_is_tenant_member_bloqueia_outro_tenant(self, user_a, tenant_b):
        request = SimpleNamespace(user=user_a, tenant=tenant_b)

        assert IsTenantMember().has_permission(request, view=None) is False

    def test_is_device_token_permite_token_device_valido(self, tenant_a):
        token = AccessToken()
        token["is_device"] = True
        token["tenant_id"] = str(tenant_a.id)
        token["device_id"] = "tablet-01"

        request = SimpleNamespace(auth=token, tenant=tenant_a)

        assert IsDeviceToken().has_permission(request, view=None) is True

    def test_is_device_token_bloqueia_quando_tenant_diferente(self, tenant_a, tenant_b):
        token = AccessToken()
        token["is_device"] = True
        token["tenant_id"] = str(tenant_a.id)

        request = SimpleNamespace(auth=token, tenant=tenant_b)

        assert IsDeviceToken().has_permission(request, view=None) is False


@pytest.mark.django_db
class TestDeviceRegisterEndpoint:
    endpoint = "/api/auth/device/register/"

    def test_registra_device_e_retorna_token_de_dispositivo(self, tenant_a, user_a):
        client = APIClient()
        client.force_authenticate(user=user_a)

        payload = {"device_id": "tablet-entrada-01", "nome": "Portaria 1"}
        response = client.post(
            self.endpoint,
            data=payload,
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 201
        assert Device.objects.filter(tenant=tenant_a, device_id="tablet-entrada-01").exists()

        access = AccessToken(response.data["access"])
        assert access["is_device"] is True
        assert access["tenant_id"] == str(tenant_a.id)
        assert access["device_id"] == "tablet-entrada-01"

    def test_bloqueia_usuario_de_tenant_diferente(self, tenant_a, tenant_b, user_b):
        client = APIClient()
        client.force_authenticate(user=user_b)

        response = client.post(
            self.endpoint,
            data={"device_id": "tablet-entrada-02"},
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 403
        assert not Device.objects.filter(tenant=tenant_a, device_id="tablet-entrada-02").exists()

    def test_update_do_device_existente(self, tenant_a, user_a):
        Device.objects.create(tenant=tenant_a, device_id="tablet-entrada-03", nome="Antigo")
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.post(
            self.endpoint,
            data={"device_id": "tablet-entrada-03", "nome": "Novo Nome"},
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 200

        device = Device.objects.get(tenant=tenant_a, device_id="tablet-entrada-03")
        assert device.nome == "Novo Nome"
        assert device.last_seen_at is not None
