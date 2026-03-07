import base64
import io
import json

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.biometrics.models import ConsentimentoBiometrico, FacialEmbedding
from apps.biometrics.services import BiometriaService, assert_active_consent, has_active_consent
from apps.employees.models import Employee
from apps.tenants.models import Tenant

FERNET_TEST_KEY = "WjnP5UVL2Jjc4e_n1f4xQ6A9EPzh9GfG2N4BqIJVY6Q="


@pytest.fixture
def tenant_a(db):
    return Tenant.objects.create(
        cnpj="66666666000166",
        razao_social="Tenant Biometrics A",
        plano=Tenant.Plano.BASICO,
    )


@pytest.fixture
def tenant_b(db):
    return Tenant.objects.create(
        cnpj="77777777000177",
        razao_social="Tenant Biometrics B",
        plano=Tenant.Plano.PROFISSIONAL,
    )


@pytest.fixture
def user_a(db, tenant_a):
    return User.objects.create_user(
        email="gestor@bio-a.com",
        password="12345678",
        tenant=tenant_a,
        role=User.Role.GESTOR,
    )


@pytest.fixture
def user_b(db, tenant_b):
    return User.objects.create_user(
        email="gestor@bio-b.com",
        password="12345678",
        tenant=tenant_b,
        role=User.Role.GESTOR,
    )


@pytest.fixture
def employee_a(db, tenant_a):
    return Employee.all_objects.create(
        tenant=tenant_a,
        nome="Funcionario A",
        cpf="88888888001",
        pis="99999999001",
        email="func.a@empresa.com",
        ativo=True,
    )


@pytest.fixture
def employee_b(db, tenant_b):
    return Employee.all_objects.create(
        tenant=tenant_b,
        nome="Funcionario B",
        cpf="88888888002",
        pis="99999999002",
        email="func.b@empresa.com",
        ativo=True,
    )


@pytest.fixture
def biometria_key(settings):
    settings.BIOMETRIA_KEY = FERNET_TEST_KEY
    return settings.BIOMETRIA_KEY


def _build_test_image_file(name="face.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


def _device_access_token_for(user, tenant_id, device_id="tablet-main"):
    refresh = RefreshToken.for_user(user)
    refresh["tenant_id"] = str(tenant_id)
    refresh["role"] = "device"
    refresh["is_device"] = True
    refresh["device_id"] = device_id
    return str(refresh.access_token)


@pytest.mark.django_db
class TestConsentService:
    def test_has_active_consent_false_sem_registro(self, employee_a):
        assert has_active_consent(employee_a) is False

    def test_has_active_consent_considera_ultimo_registro(self, employee_a):
        ConsentimentoBiometrico.objects.create(
            employee=employee_a,
            aceito=True,
            versao_termo="v1",
        )
        ConsentimentoBiometrico.objects.create(
            employee=employee_a,
            aceito=False,
            versao_termo="v2",
        )

        assert has_active_consent(employee_a) is False

    def test_assert_active_consent_levanta_exception(self, employee_a):
        with pytest.raises(PermissionDenied):
            assert_active_consent(employee_a)


@pytest.mark.django_db
class TestBiometriaService:
    class AdapterSucesso:
        @staticmethod
        def represent(image_bytes):
            return [{"embedding": [0.11, 0.22, 0.33]}]

    class AdapterSemRosto:
        @staticmethod
        def represent(image_bytes):
            return []

    class AdapterMultiplosRostos:
        @staticmethod
        def represent(image_bytes):
            return [{"embedding": [0.1]}, {"embedding": [0.2]}]

    class AdapterVerifySucesso:
        @staticmethod
        def represent(image_bytes):
            return [{"embedding": [0.44, 0.55, 0.66]}]

        @staticmethod
        def verify(captured_embedding, stored_embedding):
            assert captured_embedding == [0.44, 0.55, 0.66]
            assert stored_embedding == [0.11, 0.22, 0.33]
            return {"verified": True, "distance": 0.41, "threshold": 0.68}

    class AdapterVerifySemRosto:
        @staticmethod
        def represent(image_bytes):
            return []

        @staticmethod
        def verify(captured_embedding, stored_embedding):
            return {"verified": False, "distance": 1.0, "threshold": 0.68}

    def test_bloqueia_cadastro_sem_consentimento(self, employee_a, biometria_key):
        service = BiometriaService(adapter=self.AdapterSucesso)

        with pytest.raises(PermissionDenied):
            service.cadastrar_embedding(employee_a, b"fake-image")

    def test_cadastra_embedding_criptografado_e_inativa_anterior(
        self,
        employee_a,
        biometria_key,
    ):
        ConsentimentoBiometrico.objects.create(
            employee=employee_a,
            aceito=True,
            versao_termo="v1",
        )
        service = BiometriaService(adapter=self.AdapterSucesso)

        primeiro = service.cadastrar_embedding(employee_a, b"img-1")
        segundo = service.cadastrar_embedding(employee_a, b"img-2")

        primeiro.refresh_from_db()
        segundo.refresh_from_db()

        assert primeiro.ativo is False
        assert segundo.ativo is True
        assert FacialEmbedding.objects.filter(employee=employee_a).count() == 2

        embedding_data = segundo.embedding_data
        if isinstance(embedding_data, memoryview):
            embedding_data = embedding_data.tobytes()

        embedding_raw = Fernet(biometria_key.encode()).decrypt(embedding_data)
        assert json.loads(embedding_raw.decode("utf-8")) == [0.11, 0.22, 0.33]

    def test_exige_exatamente_um_rosto(self, employee_a, biometria_key):
        ConsentimentoBiometrico.objects.create(
            employee=employee_a,
            aceito=True,
            versao_termo="v1",
        )
        service_sem_rosto = BiometriaService(adapter=self.AdapterSemRosto)
        service_multiplos = BiometriaService(adapter=self.AdapterMultiplosRostos)

        with pytest.raises(ValidationError):
            service_sem_rosto.cadastrar_embedding(employee_a, b"img")

        with pytest.raises(ValidationError):
            service_multiplos.cadastrar_embedding(employee_a, b"img")

    def test_verificar_retorna_payload_padrao(self, employee_a, biometria_key):
        encrypted = Fernet(biometria_key.encode()).encrypt(
            json.dumps([0.11, 0.22, 0.33]).encode("utf-8")
        )
        FacialEmbedding.objects.create(
            employee=employee_a,
            embedding_data=encrypted,
            ativo=True,
        )

        service = BiometriaService(adapter=self.AdapterVerifySucesso)
        resultado = service.verificar(employee_a, b"img")

        assert resultado == {
            "autenticado": True,
            "distancia": 0.41,
            "threshold": 0.68,
        }

    def test_verificar_bloqueia_sem_embedding_ativo(self, employee_a, biometria_key):
        service = BiometriaService(adapter=self.AdapterVerifySucesso)

        with pytest.raises(ValidationError):
            service.verificar(employee_a, b"img")

    def test_verificar_exige_um_unico_rosto(self, employee_a, biometria_key):
        encrypted = Fernet(biometria_key.encode()).encrypt(
            json.dumps([0.11, 0.22, 0.33]).encode("utf-8")
        )
        FacialEmbedding.objects.create(
            employee=employee_a,
            embedding_data=encrypted,
            ativo=True,
        )

        service = BiometriaService(adapter=self.AdapterVerifySemRosto)
        with pytest.raises(ValidationError):
            service.verificar(employee_a, b"img")


@pytest.mark.django_db
class TestEmployeeConsentEndpoint:
    def test_registra_consentimento(self, tenant_a, user_a, employee_a):
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.post(
            f"/api/employees/{employee_a.id}/consent/",
            data={"aceito": True, "versao_termo": "v1"},
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
            REMOTE_ADDR="10.10.10.10",
        )

        assert response.status_code == 201
        assert response.data["employee"] == employee_a.id
        assert response.data["aceito"] is True
        assert response.data["versao_termo"] == "v1"
        assert response.data["ip_origem"] == "10.10.10.10"

        assert ConsentimentoBiometrico.objects.filter(employee=employee_a).count() == 1

    def test_bloqueia_consentimento_de_outro_tenant(self, tenant_a, user_a, employee_b):
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.post(
            f"/api/employees/{employee_b.id}/consent/",
            data={"aceito": True, "versao_termo": "v1"},
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 404

    def test_bloqueia_usuario_de_tenant_diferente(self, tenant_a, user_b, employee_a):
        client = APIClient()
        client.force_authenticate(user=user_b)

        response = client.post(
            f"/api/employees/{employee_a.id}/consent/",
            data={"aceito": True, "versao_termo": "v1"},
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestEmployeeEnrollEndpoint:
    def test_bloqueia_enroll_sem_consentimento(self, tenant_a, user_a, employee_a, biometria_key):
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.post(
            f"/api/employees/{employee_a.id}/enroll/",
            data={"imagem": _build_test_image_file()},
            format="multipart",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 403

    def test_realiza_enroll_com_consentimento(self, tenant_a, user_a, employee_a, monkeypatch):
        ConsentimentoBiometrico.objects.create(
            employee=employee_a,
            aceito=True,
            versao_termo="v1",
        )

        def fake_cadastrar_embedding(self, employee, imagem_bytes):
            assert employee.id == employee_a.id
            assert imagem_bytes
            return FacialEmbedding.objects.create(
                employee=employee_a,
                embedding_data=b"encrypted",
                ativo=True,
            )

        monkeypatch.setattr(
            "apps.biometrics.views.BiometriaService.cadastrar_embedding",
            fake_cadastrar_embedding,
        )

        client = APIClient()
        client.force_authenticate(user=user_a)
        response = client.post(
            f"/api/employees/{employee_a.id}/enroll/",
            data={"imagem": _build_test_image_file()},
            format="multipart",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 201
        assert response.data["employee"] == employee_a.id
        assert response.data["ativo"] is True
        assert FacialEmbedding.objects.filter(employee=employee_a, ativo=True).count() == 1

    def test_bloqueia_enroll_de_outro_tenant(self, tenant_a, user_a, employee_b):
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.post(
            f"/api/employees/{employee_b.id}/enroll/",
            data={"imagem": _build_test_image_file()},
            format="multipart",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestBiometricVerifyEndpoint:
    endpoint = "/api/biometrics/verify/"

    def test_verifica_biometria_com_token_device(self, tenant_a, user_a, employee_a, monkeypatch):
        def fake_verificar(self, employee, imagem_bytes):
            assert employee.id == employee_a.id
            assert imagem_bytes
            return {"autenticado": True, "distancia": 0.51, "threshold": 0.68}

        monkeypatch.setattr(
            "apps.biometrics.views.BiometriaService.verificar",
            fake_verificar,
        )

        token = _device_access_token_for(user_a, tenant_a.id, device_id="tablet-a")
        client = APIClient()
        response = client.post(
            self.endpoint,
            data={"employee_id": employee_a.id, "imagem": _build_test_image_file()},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 200
        assert response.data == {"autenticado": True, "distancia": 0.51, "threshold": 0.68}

    def test_bloqueia_token_nao_device(self, tenant_a, user_a, employee_a):
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.post(
            self.endpoint,
            data={"employee_id": employee_a.id, "imagem": _build_test_image_file()},
            format="multipart",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 403

    def test_bloqueia_funcionario_de_outro_tenant(self, tenant_a, user_a, employee_b):
        token = _device_access_token_for(user_a, tenant_a.id, device_id="tablet-a")
        client = APIClient()
        response = client.post(
            self.endpoint,
            data={"employee_id": employee_b.id, "imagem": _build_test_image_file()},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestEmployeeEmbeddingsEndpoint:
    endpoint = "/api/employees/embeddings/"

    def test_lista_apenas_embeddings_ativos_do_tenant_do_device(
        self,
        tenant_a,
        tenant_b,
        user_a,
        employee_a,
        employee_b,
    ):
        employee_inativo = Employee.all_objects.create(
            tenant=tenant_a,
            nome="Funcionario Inativo",
            cpf="88888888003",
            pis="99999999003",
            email="func.inativo@empresa.com",
            ativo=False,
        )

        FacialEmbedding.objects.create(
            employee=employee_a,
            embedding_data=b"a-inativo",
            ativo=False,
        )
        FacialEmbedding.objects.create(
            employee=employee_a,
            embedding_data=b"a-ativo",
            ativo=True,
        )
        FacialEmbedding.objects.create(
            employee=employee_inativo,
            embedding_data=b"inativo-employee",
            ativo=True,
        )
        FacialEmbedding.objects.create(
            employee=employee_b,
            embedding_data=b"tenant-b-ativo",
            ativo=True,
        )

        token = _device_access_token_for(user_a, tenant_a.id, device_id="tablet-a")
        client = APIClient()
        response = client.get(
            self.endpoint,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["employee_id"] == employee_a.id
        assert response.data["results"][0]["embedding_encrypted"] == base64.b64encode(
            b"a-ativo"
        ).decode("ascii")
        assert response.data["results"][0]["updated_at"] is not None

    def test_bloqueia_token_nao_device(self, tenant_a, user_a):
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.get(
            self.endpoint,
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 403
