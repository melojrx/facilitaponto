import json
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.db import IntegrityError
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Device, User
from apps.accounts.permissions import CanDecideAdjustmentRequests, IsDeviceToken, IsTenantMember
from apps.accounts.serializers import TenantTokenObtainPairSerializer
from apps.accounts.services_cep import CepLookupError, CepNotFoundError
from apps.accounts.services_cnpj import (
    CnpjLookupError,
    CnpjLookupTimeoutError,
    CnpjNotFoundError,
    lookup_cnpj_via_cnpja_open,
)
from apps.accounts.services_onboarding import AccountOnboardingService
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

    def test_garante_um_owner_por_tenant(self, tenant_a):
        User.objects.create_user(
            email="owner1@tenant-a.com",
            password="12345678",
            tenant=tenant_a,
            role=User.Role.ADMIN,
            is_account_owner=True,
        )

        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="owner2@tenant-a.com",
                password="12345678",
                tenant=tenant_a,
                role=User.Role.ADMIN,
                is_account_owner=True,
            )


@pytest.mark.django_db
class TestAccountOnboardingService:
    def test_create_owner_account(self):
        user = AccountOnboardingService.create_owner_account(
            first_name="Joao",
            last_name="Silva",
            email="owner@novo.com",
            cpf="39053344705",
            phone="85999998888",
            password="SenhaForte123!",
        )

        assert user.email == "owner@novo.com"
        assert user.cpf == "39053344705"
        assert user.is_account_owner is True

    def test_upsert_company_for_owner_vincula_owner(self):
        owner = User.objects.create_user(
            email="owner@service.com",
            cpf="70379043036",
            password="SenhaForte123!",
            role=User.Role.ADMIN,
            is_account_owner=True,
        )

        tenant = AccountOnboardingService.upsert_company_for_owner(
            owner=owner,
            company_data={
                "tipo_pessoa": Tenant.TipoPessoa.PJ,
                "documento": "50529647000183",
                "razao_social": "Acme Service LTDA",
                "nome_fantasia": "Acme",
                "email_contato": "contato@acme.com",
                "telefone_contato": "85999998888",
                "cep": "60711165",
                "logradouro": "Rua A",
                "numero": "100",
                "complemento": "",
                "bairro": "Centro",
                "cidade": "Fortaleza",
                "estado": "CE",
                "responsavel_nome": "Joao",
                "responsavel_cpf": "39053344705",
                "responsavel_cargo": "Diretor",
                "logo_url": "",
                "website": "",
                "cno_caepf": "",
                "inscricao_estadual": "",
                "inscricao_municipal": "",
            },
        )

        owner.refresh_from_db()
        assert owner.tenant_id == tenant.id
        assert owner.is_account_owner is True


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
class TestTokenObtainRateLimit:
    endpoint = "/api/auth/token/"

    @override_settings(
        AUTH_RATE_LIMITS={
            "web_login": {"limit": 10, "window_seconds": 60},
            "web_signup": {"limit": 5, "window_seconds": 60},
            "api_token": {"limit": 2, "window_seconds": 60},
        }
    )
    def test_aplica_rate_limit_no_token_obtain_pair(self, user_a):
        cache.clear()
        client = APIClient()
        payload = {"email": user_a.email, "password": "senha-errada"}

        first_response = client.post(self.endpoint, data=payload, format="json")
        second_response = client.post(self.endpoint, data=payload, format="json")
        third_response = client.post(self.endpoint, data=payload, format="json")

        assert first_response.status_code == 401
        assert second_response.status_code == 401
        assert third_response.status_code == 429
        assert "Muitas tentativas de autenticação" in third_response.data["detail"]


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

    def test_can_decide_adjustment_requests_permite_admin(self, user_a, tenant_a):
        request = SimpleNamespace(user=user_a, tenant=tenant_a)

        assert CanDecideAdjustmentRequests().has_permission(request, view=None) is True

    def test_can_decide_adjustment_requests_bloqueia_viewer(self, tenant_a):
        viewer = User.objects.create_user(
            email="viewer-adjustments@tenant-a.com",
            password="12345678",
            tenant=tenant_a,
            role=User.Role.VIEWER,
        )
        request = SimpleNamespace(user=viewer, tenant=tenant_a)

        assert CanDecideAdjustmentRequests().has_permission(request, view=None) is False


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


@pytest.mark.django_db
class TestPublicCepLookupEndpoint:
    endpoint = "/api/public/cep/"

    def test_consulta_cep_com_sucesso(self, monkeypatch):
        monkeypatch.setattr(
            "apps.accounts.views.lookup_cep_via_viacep",
            lambda cep: {
                "cep": cep,
                "logradouro": "Rua das Flores",
                "bairro": "Centro",
                "cidade": "Fortaleza",
                "estado": "CE",
            },
        )
        client = APIClient()

        response = client.get(self.endpoint, {"cep": "60711-165"})

        assert response.status_code == 200
        assert response.data["ok"] is True
        assert response.data["data"]["cep"] == "60711165"
        assert response.data["data"]["cidade"] == "Fortaleza"

    def test_consulta_cep_invalido(self):
        client = APIClient()

        response = client.get(self.endpoint, {"cep": "123"})

        assert response.status_code == 400
        assert "cep" in response.data

    def test_consulta_cep_nao_encontrado(self, monkeypatch):
        def _raise_not_found(*args, **kwargs):
            raise CepNotFoundError("not found")

        monkeypatch.setattr("apps.accounts.views.lookup_cep_via_viacep", _raise_not_found)
        client = APIClient()

        response = client.get(self.endpoint, {"cep": "00000-000"})

        assert response.status_code == 404
        assert response.data["ok"] is False
        assert response.data["code"] == "cep_not_found"

    def test_consulta_cep_servico_indisponivel(self, monkeypatch):
        def _raise_unavailable(*args, **kwargs):
            raise CepLookupError("unavailable")

        monkeypatch.setattr("apps.accounts.views.lookup_cep_via_viacep", _raise_unavailable)
        client = APIClient()

        response = client.get(self.endpoint, {"cep": "60711165"})

        assert response.status_code == 503
        assert response.data["ok"] is False
        assert response.data["code"] == "provider_unavailable"


class DummyHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.django_db
class TestCnpjLookupService:
    def test_normaliza_payload_e_sinaliza_preenchimento_parcial(self, monkeypatch):
        monkeypatch.setattr(
            "apps.accounts.services_cnpj.urlopen",
            lambda request, timeout=4.0: DummyHTTPResponse(
                {
                    "company": {"name": "Acme LTDA", "alias": "Acme"},
                    "address": {
                        "street": "Rua das Flores",
                        "district": "Centro",
                        "city": {"name": "Fortaleza"},
                        "state": {"code": "CE"},
                        "zip": "60711-165",
                    },
                    "emails": [{"address": "contato@acme.com"}],
                }
            ),
        )

        result = lookup_cnpj_via_cnpja_open("50.529.647/0001-83")

        assert result["data"]["documento"] == "50529647000183"
        assert result["data"]["razao_social"] == "Acme LTDA"
        assert result["data"]["email_contato"] == "contato@acme.com"
        assert result["data"]["cep"] == "60711165"
        assert result["meta"]["partial"] is True
        assert "telefone_contato" in result["meta"]["missing_fields"]
        assert "telefone" in result["meta"]["missing_labels"]

    def test_timeout_do_provider_gera_erro_especifico(self, monkeypatch):
        def _raise_timeout(*args, **kwargs):
            raise TimeoutError("timeout")

        monkeypatch.setattr("apps.accounts.services_cnpj.urlopen", _raise_timeout)

        with pytest.raises(CnpjLookupTimeoutError):
            lookup_cnpj_via_cnpja_open("50529647000183")

    def test_http_404_vira_cnpj_nao_encontrado(self, monkeypatch):
        from urllib.error import HTTPError

        def _raise_not_found(*args, **kwargs):
            raise HTTPError(
                url="https://open.cnpja.com/office/50529647000183",
                code=404,
                msg="not found",
                hdrs=None,
                fp=None,
            )

        monkeypatch.setattr("apps.accounts.services_cnpj.urlopen", _raise_not_found)

        with pytest.raises(CnpjNotFoundError):
            lookup_cnpj_via_cnpja_open("50529647000183")


@pytest.mark.django_db
class TestPublicCnpjLookupEndpoint:
    endpoint = "/api/public/cnpj/"

    def test_consulta_cnpj_com_sucesso(self, monkeypatch):
        monkeypatch.setattr(
            "apps.accounts.views.lookup_cnpj_via_cnpja_open",
            lambda cnpj: {
                "data": {
                    "documento": cnpj,
                    "razao_social": "Acme LTDA",
                    "nome_fantasia": "Acme",
                    "email_contato": "contato@acme.com",
                    "telefone_contato": "85999998888",
                    "cep": "60711165",
                    "logradouro": "Rua das Flores",
                    "numero": "100",
                    "complemento": "",
                    "bairro": "Centro",
                    "cidade": "Fortaleza",
                    "estado": "CE",
                },
                "meta": {
                    "provider": "cnpja_open",
                    "partial": False,
                    "missing_fields": [],
                    "missing_labels": [],
                },
            },
        )
        client = APIClient()

        response = client.get(self.endpoint, {"cnpj": "50.529.647/0001-83"})

        assert response.status_code == 200
        assert response.data["ok"] is True
        assert response.data["data"]["documento"] == "50529647000183"
        assert response.data["meta"]["partial"] is False

    def test_consulta_cnpj_invalido(self):
        client = APIClient()

        response = client.get(self.endpoint, {"cnpj": "123"})

        assert response.status_code == 400
        assert "cnpj" in response.data

    def test_consulta_cnpj_nao_encontrado(self, monkeypatch):
        def _raise_not_found(*args, **kwargs):
            raise CnpjNotFoundError("not found")

        monkeypatch.setattr("apps.accounts.views.lookup_cnpj_via_cnpja_open", _raise_not_found)
        client = APIClient()

        response = client.get(self.endpoint, {"cnpj": "50.529.647/0001-83"})

        assert response.status_code == 404
        assert response.data["ok"] is False
        assert response.data["code"] == "cnpj_not_found"
        assert response.data["manual_fallback"] is True

    def test_consulta_cnpj_timeout(self, monkeypatch):
        def _raise_timeout(*args, **kwargs):
            raise CnpjLookupTimeoutError("timeout")

        monkeypatch.setattr("apps.accounts.views.lookup_cnpj_via_cnpja_open", _raise_timeout)
        client = APIClient()

        response = client.get(self.endpoint, {"cnpj": "50.529.647/0001-83"})

        assert response.status_code == 504
        assert response.data["ok"] is False
        assert response.data["code"] == "provider_timeout"
        assert response.data["manual_fallback"] is True

    def test_consulta_cnpj_servico_indisponivel(self, monkeypatch):
        def _raise_unavailable(*args, **kwargs):
            raise CnpjLookupError("unavailable")

        monkeypatch.setattr("apps.accounts.views.lookup_cnpj_via_cnpja_open", _raise_unavailable)
        client = APIClient()

        response = client.get(self.endpoint, {"cnpj": "50.529.647/0001-83"})

        assert response.status_code == 503
        assert response.data["ok"] is False
        assert response.data["code"] == "provider_unavailable"
        assert response.data["manual_fallback"] is True
