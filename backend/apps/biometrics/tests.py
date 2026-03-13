import base64
import io
import json
from datetime import timedelta
from types import SimpleNamespace
from urllib import error

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.biometrics.forms import AssistedBiometricCaptureForm
from apps.biometrics.models import BiometricInvite, ConsentimentoBiometrico, FacialEmbedding
from apps.biometrics.providers import WahaWhatsAppProvider
from apps.biometrics.services import (
    AssistedBiometricCaptureService,
    BiometriaService,
    BiometricInviteService,
    assert_active_consent,
    has_active_consent,
)
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


def _build_test_image_data_url():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


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


@pytest.mark.django_db
class TestAssistedBiometricCaptureService:
    class AdapterSucesso:
        @staticmethod
        def represent(image_bytes):
            return [{"embedding": [0.11, 0.22, 0.33]}]

    class AdapterSemRosto:
        @staticmethod
        def represent(image_bytes):
            return []

    class AdapterVerifySemRosto:
        @staticmethod
        def represent(image_bytes):
            return []

        @staticmethod
        def verify(captured_embedding, stored_embedding):
            return {"verified": False, "distance": 1.0, "threshold": 0.68}

    def test_captura_assistida_registra_consentimento_e_embedding(
        self,
        employee_a,
        biometria_key,
    ):
        service = AssistedBiometricCaptureService(
            biometria_service=BiometriaService(adapter=self.AdapterSucesso)
        )

        result = service.capture_for_panel(
            employee=employee_a,
            imagem_bytes=b"img",
            consentimento_aceito=True,
            versao_termo="painel-v1",
            ip_origem="10.0.0.1",
        )

        assert result["consent"].aceito is True
        assert result["consent"].versao_termo == "painel-v1"
        assert result["consent"].ip_origem == "10.0.0.1"
        assert result["embedding"].ativo is True
        assert result["snapshot"]["status"] == Employee.BiometricStatus.CADASTRADA
        assert ConsentimentoBiometrico.objects.filter(employee=employee_a).count() == 1
        assert FacialEmbedding.objects.filter(employee=employee_a, ativo=True).count() == 1

    def test_bloqueia_sem_consentimento(self, employee_a, biometria_key):
        service = AssistedBiometricCaptureService(
            biometria_service=BiometriaService(adapter=self.AdapterSucesso)
        )

        with pytest.raises(ValidationError, match="Marque a autoriza"):
            service.capture_for_panel(
                employee=employee_a,
                imagem_bytes=b"img",
                consentimento_aceito=False,
            )

        assert ConsentimentoBiometrico.objects.filter(employee=employee_a).count() == 0
        assert FacialEmbedding.objects.filter(employee=employee_a).count() == 0

    def test_bloqueia_sem_imagem(self, employee_a, biometria_key):
        service = AssistedBiometricCaptureService(
            biometria_service=BiometriaService(adapter=self.AdapterSucesso)
        )

        with pytest.raises(ValidationError, match="foto facial"):
            service.capture_for_panel(
                employee=employee_a,
                imagem_bytes=b"",
                consentimento_aceito=True,
            )

        assert ConsentimentoBiometrico.objects.filter(employee=employee_a).count() == 0
        assert FacialEmbedding.objects.filter(employee=employee_a).count() == 0

    def test_falha_de_enroll_preserva_consentimento_e_estado_pendente(
        self,
        employee_a,
        biometria_key,
    ):
        service = AssistedBiometricCaptureService(
            biometria_service=BiometriaService(adapter=self.AdapterSemRosto)
        )

        with pytest.raises(ValidationError, match="Nenhum rosto detectado"):
            service.capture_for_panel(
                employee=employee_a,
                imagem_bytes=b"img",
                consentimento_aceito=True,
                versao_termo="painel-v1",
            )

        employee_a.refresh_from_db()
        assert ConsentimentoBiometrico.objects.filter(employee=employee_a, aceito=True).count() == 1
        assert FacialEmbedding.objects.filter(employee=employee_a).count() == 0
        assert employee_a.biometric_status == Employee.BiometricStatus.CONSENTIMENTO

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


class TestAssistedBiometricCaptureForm:
    def test_accepts_uploaded_image(self):
        form = AssistedBiometricCaptureForm(
            data={
                "consentimento": "on",
                "versao_termo": "painel-v1",
            },
            files={"imagem": _build_test_image_file()},
        )

        assert form.is_valid() is True
        assert form.cleaned_data["imagem_bytes"]

    def test_accepts_captured_image_data_url(self):
        form = AssistedBiometricCaptureForm(
            data={
                "imagem_capturada": _build_test_image_data_url(),
                "consentimento": "on",
                "versao_termo": "painel-v1",
            }
        )

        assert form.is_valid() is True
        assert form.cleaned_data["imagem_bytes"]

    def test_rejects_without_any_image_source(self):
        form = AssistedBiometricCaptureForm(
            data={
                "consentimento": "on",
                "versao_termo": "painel-v1",
            }
        )

        assert form.is_valid() is False
        assert "Envie uma foto facial válida para continuar." in form.errors["__all__"]


@pytest.mark.django_db
class TestBiometricInviteService:
    class ProviderSucesso:
        provider_name = "fake"

        def send_biometric_invite(self, *, phone_number, message_text, metadata=None):
            return SimpleNamespace(
                provider=self.provider_name,
                message_id="msg-123",
                payload={
                    "phone_number": phone_number,
                    "message_text": message_text,
                    "metadata": metadata or {},
                },
            )

    class ProviderFalha:
        provider_name = "fake"

        def send_biometric_invite(self, *, phone_number, message_text, metadata=None):
            raise ValidationError("Falha ao enviar link por WhatsApp. Provider indisponivel.")

    def test_envia_convite_biometrico_por_whatsapp(
        self,
        employee_a,
        user_a,
        settings,
    ):
        settings.BIOMETRIC_SELF_ENROLL_BASE_URL = "https://app.facilitaponto.com/biometria/cadastro-facial"
        settings.BIOMETRIC_INVITE_EXPIRATION_HOURS = 24
        employee_a.telefone = "85999990000"
        employee_a.save(update_fields=["telefone"])

        result = BiometricInviteService(provider=self.ProviderSucesso()).send_whatsapp_invite(
            employee=employee_a,
            requested_by=user_a,
        )

        invite = result["invite"]
        assert invite.status == BiometricInvite.Status.SENT
        assert invite.sent_to == "85999990000"
        assert invite.provider == "fake"
        assert invite.provider_message_id == "msg-123"
        assert invite.created_by == user_a
        assert "token=" in result["invite_url"]
        raw_token = result["invite_url"].split("token=", 1)[1]
        assert invite.token_hash == BiometricInvite.build_token_hash(raw_token)
        assert invite.provider_payload["metadata"]["employee_id"] == employee_a.id

    def test_revoga_convite_anterior_ativo_antes_de_enviar_novo(
        self,
        employee_a,
        user_a,
        settings,
    ):
        settings.BIOMETRIC_SELF_ENROLL_BASE_URL = "https://app.facilitaponto.com/biometria/cadastro-facial"
        settings.BIOMETRIC_INVITE_EXPIRATION_HOURS = 24
        employee_a.telefone = "85999990000"
        employee_a.save(update_fields=["telefone"])

        previous = BiometricInvite.all_objects.create(
            tenant=employee_a.tenant,
            employee=employee_a,
            created_by=user_a,
            provider="fake",
            sent_to="85999990000",
            token_hash=BiometricInvite.build_token_hash("token-anterior"),
            expires_at=timezone.now() + timedelta(hours=12),
            status=BiometricInvite.Status.SENT,
        )

        BiometricInviteService(provider=self.ProviderSucesso()).send_whatsapp_invite(
            employee=employee_a,
            requested_by=user_a,
        )

        previous.refresh_from_db()
        assert previous.status == BiometricInvite.Status.REVOKED
        assert BiometricInvite.all_objects.filter(
            employee=employee_a,
            status=BiometricInvite.Status.SENT,
        ).count() == 1

    def test_bloqueia_envio_sem_telefone_valido(self, employee_a, user_a, settings):
        settings.BIOMETRIC_SELF_ENROLL_BASE_URL = "https://app.facilitaponto.com/biometria/cadastro-facial"
        settings.BIOMETRIC_INVITE_EXPIRATION_HOURS = 24
        employee_a.telefone = ""
        employee_a.save(update_fields=["telefone"])

        with pytest.raises(ValidationError, match="Telefone invalido"):
            BiometricInviteService(provider=self.ProviderSucesso()).send_whatsapp_invite(
                employee=employee_a,
                requested_by=user_a,
            )

    def test_bloqueia_envio_cross_tenant(self, employee_a, user_b, settings):
        settings.BIOMETRIC_SELF_ENROLL_BASE_URL = "https://app.facilitaponto.com/biometria/cadastro-facial"
        settings.BIOMETRIC_INVITE_EXPIRATION_HOURS = 24
        employee_a.telefone = "85999990000"
        employee_a.save(update_fields=["telefone"])

        with pytest.raises(PermissionDenied):
            BiometricInviteService(provider=self.ProviderSucesso()).send_whatsapp_invite(
                employee=employee_a,
                requested_by=user_b,
            )

    def test_falha_do_provider_marca_convite_como_failed(self, employee_a, user_a, settings):
        settings.BIOMETRIC_SELF_ENROLL_BASE_URL = "https://app.facilitaponto.com/biometria/cadastro-facial"
        settings.BIOMETRIC_INVITE_EXPIRATION_HOURS = 24
        employee_a.telefone = "85999990000"
        employee_a.save(update_fields=["telefone"])

        with pytest.raises(ValidationError, match="Falha ao enviar link por WhatsApp"):
            BiometricInviteService(provider=self.ProviderFalha()).send_whatsapp_invite(
                employee=employee_a,
                requested_by=user_a,
            )

        invite = BiometricInvite.all_objects.get(employee=employee_a)
        assert invite.status == BiometricInvite.Status.FAILED
        assert "Provider indisponivel" in invite.last_error

    def test_get_invite_for_token_marca_expirado(self, employee_a, user_a):
        raw_token = "token-expirado"
        invite = BiometricInvite.all_objects.create(
            tenant=employee_a.tenant,
            employee=employee_a,
            created_by=user_a,
            provider="fake",
            sent_to="85999990000",
            token_hash=BiometricInvite.build_token_hash(raw_token),
            expires_at=timezone.now() - timedelta(minutes=5),
            status=BiometricInvite.Status.SENT,
        )

        with pytest.raises(ValidationError, match="expirou"):
            BiometricInviteService(provider=self.ProviderSucesso()).get_invite_for_token(
                raw_token=raw_token
            )

        invite.refresh_from_db()
        assert invite.status == BiometricInvite.Status.EXPIRED

    def test_complete_self_enroll_consumes_invite(self, employee_a, user_a, biometria_key):
        class AdapterBiometriaSucesso:
            @staticmethod
            def represent(image_bytes):
                return [{"embedding": [0.11, 0.22, 0.33]}]

        raw_token = "token-valido"
        invite = BiometricInvite.all_objects.create(
            tenant=employee_a.tenant,
            employee=employee_a,
            created_by=user_a,
            provider="fake",
            sent_to="85999990000",
            token_hash=BiometricInvite.build_token_hash(raw_token),
            expires_at=timezone.now() + timedelta(hours=1),
            status=BiometricInvite.Status.SENT,
        )

        service = BiometricInviteService(
            provider=self.ProviderSucesso(),
            assisted_capture_service=AssistedBiometricCaptureService(
                biometria_service=BiometriaService(adapter=AdapterBiometriaSucesso())
            ),
        )

        result = service.complete_self_enroll(
            raw_token=raw_token,
            imagem_bytes=b"img",
            consentimento_aceito=True,
            versao_termo="whatsapp-v1",
            ip_origem="10.0.0.1",
        )

        invite.refresh_from_db()
        assert invite.status == BiometricInvite.Status.USED
        assert invite.used_at is not None
        assert result["snapshot"]["status"] == Employee.BiometricStatus.CADASTRADA

    def test_complete_self_enroll_bloqueia_reuso(self, employee_a, user_a):
        raw_token = "token-usado"
        invite = BiometricInvite.all_objects.create(
            tenant=employee_a.tenant,
            employee=employee_a,
            created_by=user_a,
            provider="fake",
            sent_to="85999990000",
            token_hash=BiometricInvite.build_token_hash(raw_token),
            expires_at=timezone.now() + timedelta(hours=1),
            status=BiometricInvite.Status.USED,
            used_at=timezone.now(),
        )

        with pytest.raises(ValidationError, match="ja foi utilizado"):
            BiometricInviteService(provider=self.ProviderSucesso()).complete_self_enroll(
                raw_token=raw_token,
                imagem_bytes=b"img",
                consentimento_aceito=True,
            )

        invite.refresh_from_db()
        assert invite.status == BiometricInvite.Status.USED


class TestWahaWhatsAppProvider:
    def test_send_biometric_invite_retorna_message_id(self, monkeypatch):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"message": {"id": "waha-msg-1"}}).encode("utf-8")

        captured = {}

        def fake_urlopen(http_request, timeout):
            captured["url"] = http_request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(http_request.data.decode("utf-8"))
            return FakeResponse()

        monkeypatch.setattr("apps.biometrics.providers.request.urlopen", fake_urlopen)

        provider = WahaWhatsAppProvider(
            base_url="http://waha:3000",
            session_name="default",
            api_token="token-123",
            timeout=7.5,
        )

        result = provider.send_biometric_invite(
            phone_number="85999990000",
            message_text="Teste",
            metadata={"invite_id": 1},
        )

        assert result.provider == "waha"
        assert result.message_id == "waha-msg-1"
        assert captured["url"] == "http://waha:3000/api/sendText"
        assert captured["timeout"] == 7.5
        assert captured["body"]["chatId"] == "5585999990000@c.us"
        assert captured["body"]["session"] == "default"

    def test_send_biometric_invite_converte_falha_http_em_validation_error(self, monkeypatch):
        class FakeHttpError(error.HTTPError):
            def __init__(self):
                super().__init__(
                    url="http://waha:3000/api/sendText",
                    code=500,
                    msg="server error",
                    hdrs=None,
                    fp=None,
                )

            def read(self):
                return b"provider-error"

        def fake_urlopen(http_request, timeout):
            raise FakeHttpError()

        monkeypatch.setattr("apps.biometrics.providers.request.urlopen", fake_urlopen)

        provider = WahaWhatsAppProvider(
            base_url="http://waha:3000",
            session_name="default",
        )

        with pytest.raises(ValidationError, match="Falha ao enviar link por WhatsApp via WAHA"):
            provider.send_biometric_invite(
                phone_number="85999990000",
                message_text="Teste",
            )


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
