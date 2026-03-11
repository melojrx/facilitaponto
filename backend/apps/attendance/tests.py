import base64
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from botocore.exceptions import ClientError
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Device, User
from apps.attendance.models import (
    AttendanceRecord,
    TimeClock,
    TimeClockEmployeeAssignment,
    TimeClockGeofence,
)
from apps.attendance.services import AttendanceService, TimeClockService
from apps.attendance.storage import AttendancePhotoStorageService
from apps.biometrics.models import FacialEmbedding
from apps.employees.models import Employee
from apps.legal_files.models import Comprovante
from apps.tenants.models import Tenant


class FakeBiometriaService:
    def __init__(self, autenticado=True, distancia=0.2, threshold=0.68):
        self.autenticado = autenticado
        self.distancia = distancia
        self.threshold = threshold

    def verificar(self, employee, imagem_bytes):
        return {
            "autenticado": self.autenticado,
            "distancia": self.distancia,
            "threshold": self.threshold,
        }


def _device_access_token_for(user, tenant_id, device_id="tablet-main", device_pk=None):
    refresh = RefreshToken.for_user(user)
    refresh["tenant_id"] = str(tenant_id)
    refresh["role"] = "device"
    refresh["is_device"] = True
    refresh["device_id"] = device_id
    if device_pk is not None:
        refresh["device_pk"] = str(device_pk)
    return str(refresh.access_token)


def _build_test_image_file(name="face.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


def _prepare_operational_clock(*, tenant, user, employee, device=None):
    device = device or Device.objects.create(
        tenant=tenant,
        device_id="tablet-main",
        nome="Tablet Principal",
    )
    time_clock = TimeClock.all_objects.create(
        tenant=tenant,
        created_by=user,
        nome=f"Relogio {device.device_id}",
        activation_code="AB12CD",
        current_device=device,
        status=TimeClock.Status.ATIVO,
        plataforma=TimeClock.Plataforma.ANDROID,
    )
    TimeClockEmployeeAssignment.all_objects.create(
        tenant=tenant,
        time_clock=time_clock,
        employee=employee,
    )
    FacialEmbedding.objects.create(
        employee=employee,
        embedding_data=b"embedding",
        ativo=True,
    )
    return time_clock, device


@pytest.fixture(autouse=True)
def _mock_storage_upload(monkeypatch, request):
    if "TestAttendancePhotoStorageService" in request.node.nodeid:
        return

    def fake_upload(self, tenant_id, timestamp, foto_hash, imagem_bytes, content_type="image/jpeg"):
        day = timestamp.strftime("%Y/%m/%d")
        return f"s3://ponto-digital/attendance/{tenant_id}/{day}/{foto_hash}.jpg"

    monkeypatch.setattr(
        "apps.attendance.storage.AttendancePhotoStorageService.upload_attendance_photo",
        fake_upload,
    )


@pytest.mark.django_db
class TestAttendancePhotoStorageService:
    class FakeS3Client:
        def __init__(self):
            self.head_bucket_calls = []
            self.create_bucket_calls = []
            self.put_object_calls = []
            self.raise_no_bucket_once = True

        def head_bucket(self, Bucket):
            self.head_bucket_calls.append(Bucket)
            if self.raise_no_bucket_once:
                self.raise_no_bucket_once = False
                error_response = {"Error": {"Code": "404"}}
                raise ClientError(error_response, "HeadBucket")

        def create_bucket(self, Bucket):
            self.create_bucket_calls.append(Bucket)

        def put_object(self, **kwargs):
            self.put_object_calls.append(kwargs)

    def test_upload_attendance_photo_cria_bucket_quando_ausente(self, settings):
        settings.AWS_STORAGE_BUCKET_NAME = "bucket-teste"
        fake_client = self.FakeS3Client()
        service = AttendancePhotoStorageService(client=fake_client)
        timestamp = timezone.now()

        result = service.upload_attendance_photo(
            tenant_id="tenant-1",
            timestamp=timestamp,
            foto_hash="abc123",
            imagem_bytes=b"img",
        )

        expected_key = f"attendance/tenant-1/{timestamp.strftime('%Y/%m/%d')}/abc123.jpg"
        assert result == f"s3://bucket-teste/{expected_key}"
        assert fake_client.create_bucket_calls == ["bucket-teste"]
        assert fake_client.put_object_calls[0]["Bucket"] == "bucket-teste"
        assert fake_client.put_object_calls[0]["Key"] == expected_key
        assert fake_client.put_object_calls[0]["Body"] == b"img"


@pytest.fixture
def tenant_a(db):
    return Tenant.objects.create(
        cnpj="55555555000155",
        razao_social="Tenant Attendance A",
        plano=Tenant.Plano.BASICO,
    )


@pytest.fixture
def tenant_b(db):
    return Tenant.objects.create(
        cnpj="99999999000199",
        razao_social="Tenant Attendance B",
        plano=Tenant.Plano.PROFISSIONAL,
    )


@pytest.fixture
def user_a(db, tenant_a):
    return User.objects.create_user(
        email="attendance@tenant-a.com",
        password="12345678",
        tenant=tenant_a,
        role=User.Role.ADMIN,
    )


@pytest.fixture
def user_b(db, tenant_b):
    return User.objects.create_user(
        email="attendance@tenant-b.com",
        password="12345678",
        tenant=tenant_b,
        role=User.Role.ADMIN,
    )


@pytest.fixture
def device_a(db, tenant_a):
    return Device.objects.create(
        tenant=tenant_a,
        device_id="tablet-portaria-a",
        nome="Portaria A",
    )


@pytest.fixture
def device_b(db, tenant_b):
    return Device.objects.create(
        tenant=tenant_b,
        device_id="tablet-portaria-b",
        nome="Portaria B",
    )


@pytest.fixture
def employee_a(db, tenant_a):
    return Employee.all_objects.create(
        tenant=tenant_a,
        nome="Funcionario Attendance A",
        cpf="55555555001",
        pis="55555555001",
        email="func.a@attendance.com",
        ativo=True,
    )


@pytest.fixture
def employee_b(db, tenant_b):
    return Employee.all_objects.create(
        tenant=tenant_b,
        nome="Funcionario Attendance B",
        cpf="99999999001",
        pis="99999999001",
        email="func.b@attendance.com",
        ativo=True,
    )


@pytest.mark.django_db
class TestAttendanceRecordModel:
    def test_registro_e_imutavel_apos_criacao(self, tenant_a, employee_a):
        record = AttendanceRecord.all_objects.create(
            tenant=tenant_a,
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.ENTRADA,
            timestamp=timezone.now(),
            nsr=1,
            foto_path="attendance/foto.jpg",
            foto_hash="a" * 64,
            confianca_biometrica=0.8,
            origem=AttendanceRecord.Origem.ONLINE,
        )

        record.tipo = AttendanceRecord.Tipo.SAIDA
        with pytest.raises(ValidationError):
            record.save()


@pytest.mark.django_db
class TestTimeClockModels:
    def test_relogio_bloqueia_device_de_outro_tenant(self, tenant_a, user_a, device_b):
        time_clock = TimeClock(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="AB12CD",
            current_device=device_b,
        )

        with pytest.raises(ValidationError):
            time_clock.full_clean()

    def test_relogio_bloqueia_metodo_diferente_de_facial(self, tenant_a, user_a):
        time_clock = TimeClock(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="AB12CD",
            metodo_autenticacao="PIN",
        )

        with pytest.raises(ValidationError):
            time_clock.full_clean()

    def test_cerca_virtual_bloqueia_relogio_de_outro_tenant(self, tenant_a, tenant_b, user_a):
        time_clock = TimeClock.all_objects.create(
            tenant=tenant_b,
            created_by=user_a,
            nome="Relogio B",
            activation_code="ZX12CV",
        )
        geofence = TimeClockGeofence(
            tenant=tenant_a,
            time_clock=time_clock,
            latitude=-3.731861,
            longitude=-38.52667,
            raio_metros=120,
        )

        with pytest.raises(ValidationError):
            geofence.full_clean()

    def test_vinculo_bloqueia_colaborador_de_outro_tenant(
        self,
        tenant_a,
        employee_b,
        user_a,
    ):
        time_clock = TimeClock.all_objects.create(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio A",
            activation_code="MN45OP",
        )
        assignment = TimeClockEmployeeAssignment(
            tenant=tenant_a,
            time_clock=time_clock,
            employee=employee_b,
        )

        with pytest.raises(ValidationError):
            assignment.full_clean()


@pytest.mark.django_db
class TestAttendanceService:
    def test_primeira_batida_deve_ser_entrada(self, employee_a):
        service = AttendanceService(biometria_service=FakeBiometriaService())

        with pytest.raises(ValidationError):
            service.registrar(
                employee=employee_a,
                tipo=AttendanceRecord.Tipo.SAIDA,
                imagem_bytes=b"img",
            )

    def test_ordem_das_batidas_e_validada(self, employee_a):
        service = AttendanceService(biometria_service=FakeBiometriaService())

        service.registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.ENTRADA,
            imagem_bytes=b"img-e",
        )
        with pytest.raises(ValidationError):
            service.registrar(
                employee=employee_a,
                tipo=AttendanceRecord.Tipo.ENTRADA,
                imagem_bytes=b"img-e2",
            )

        service.registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.INICIO_INTERVALO,
            imagem_bytes=b"img-ii",
        )
        service.registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.FIM_INTERVALO,
            imagem_bytes=b"img-fi",
        )
        service.registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.SAIDA,
            imagem_bytes=b"img-s",
        )
        service.registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.ENTRADA,
            imagem_bytes=b"img-e3",
        )

        tipos = list(
            AttendanceRecord.all_objects.filter(employee=employee_a)
            .order_by("nsr")
            .values_list("tipo", flat=True)
        )
        assert tipos == ["E", "II", "FI", "S", "E"]


@pytest.mark.django_db
class TestTimeClockService:
    def test_cria_relogio_com_codigo_unico_e_metodo_facial(
        self,
        tenant_a,
        user_a,
        device_a,
    ):
        service = TimeClockService()

        time_clock = service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
            descricao="Tablet principal",
            current_device=device_a,
        )

        assert time_clock.tenant == tenant_a
        assert time_clock.created_by == user_a
        assert time_clock.current_device == device_a
        assert time_clock.metodo_autenticacao == TimeClock.MetodoAutenticacao.FACIAL
        assert time_clock.status == TimeClock.Status.ATIVO
        assert len(time_clock.activation_code) == 6

    def test_bloqueia_nome_duplicado_case_insensitive(self, tenant_a, user_a):
        service = TimeClockService()
        service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
        )

        with pytest.raises(ValidationError):
            service.create_time_clock(
                tenant=tenant_a,
                user=user_a,
                nome="relogio portaria",
            )

    def test_atualiza_status_do_relogio(self, tenant_a, user_a):
        service = TimeClockService()
        time_clock = service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
        )

        updated = service.update_time_clock_status(
            time_clock=time_clock,
            status=TimeClock.Status.EM_MANUTENCAO,
        )

        assert updated.status == TimeClock.Status.EM_MANUTENCAO

    def test_regera_codigo_de_ativacao(self, tenant_a, user_a):
        service = TimeClockService()
        time_clock = service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
        )
        original_code = time_clock.activation_code

        updated = service.regenerate_activation_code(time_clock=time_clock)

        assert updated.activation_code != original_code
        assert len(updated.activation_code) == 6

    def test_configura_cerca_virtual_com_upsert(self, tenant_a, user_a):
        service = TimeClockService()
        time_clock = service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
        )

        first = service.configure_geofence(
            time_clock=time_clock,
            latitude=-3.731861,
            longitude=-38.526670,
            raio_metros=100,
        )
        second = service.configure_geofence(
            time_clock=time_clock,
            latitude=-3.731861,
            longitude=-38.526670,
            raio_metros=150,
        )

        assert first.pk == second.pk
        assert second.raio_metros == 150

    def test_atribui_e_remove_colaboradores_do_relogio(self, tenant_a, user_a):
        service = TimeClockService()
        time_clock = service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
        )
        employee = Employee.all_objects.create(
            tenant=tenant_a,
            nome="Funcionario Relogio",
            cpf="60000000001",
            pis="60000000001",
            ativo=True,
        )

        created_total = service.assign_employees(
            time_clock=time_clock,
            employee_ids=[employee.id],
        )
        removed_total = service.remove_employees(
            time_clock=time_clock,
            employee_ids=[employee.id],
        )

        assert created_total == 1
        assert removed_total == 1
        assert not TimeClockEmployeeAssignment.all_objects.filter(
            tenant=tenant_a,
            time_clock=time_clock,
            employee=employee,
        ).exists()

    def test_assign_all_considera_busca_e_colaboradores_ativos(self, tenant_a, user_a):
        service = TimeClockService()
        time_clock = service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
        )
        matching = Employee.all_objects.create(
            tenant=tenant_a,
            nome="Maria Portaria",
            cpf="60000000002",
            pis="60000000002",
            ativo=True,
        )
        Employee.all_objects.create(
            tenant=tenant_a,
            nome="Joao Fiscal",
            cpf="60000000003",
            pis="60000000003",
            ativo=True,
        )
        Employee.all_objects.create(
            tenant=tenant_a,
            nome="Maria Inativa",
            cpf="60000000004",
            pis="60000000004",
            ativo=False,
        )

        created_total = service.assign_all_employees(
            time_clock=time_clock,
            search="Maria",
        )

        assert created_total == 1
        assert TimeClockEmployeeAssignment.all_objects.filter(
            tenant=tenant_a,
            time_clock=time_clock,
            employee=matching,
        ).exists()

    def test_bloqueia_atribuicao_de_colaborador_de_outro_tenant(self, tenant_a, user_a, employee_b):
        service = TimeClockService()
        time_clock = service.create_time_clock(
            tenant=tenant_a,
            user=user_a,
            nome="Relogio Portaria",
        )

        with pytest.raises(ValidationError):
            service.assign_employees(
                time_clock=time_clock,
                employee_ids=[employee_b.id],
            )

    def test_registrar_persiste_hash_nsr_e_dados(self, employee_a):
        service = AttendanceService(
            biometria_service=FakeBiometriaService(autenticado=True, distancia=0.3)
        )

        record, created = service.registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.ENTRADA,
            imagem_bytes=b"imagem-teste",
            origem=AttendanceRecord.Origem.ONLINE,
        )

        assert created is True
        assert record.nsr == 1
        assert record.foto_hash
        assert len(record.foto_hash) == 64
        assert record.foto_path.endswith(".jpg")
        assert record.confianca_biometrica == pytest.approx(0.7)

        comprovante = Comprovante.all_objects.get(registro=record)
        assert comprovante.tenant == record.tenant
        assert comprovante.hash_carimbo
        assert len(comprovante.hash_carimbo) == 64
        assert comprovante.conteudo_json["nome"] == employee_a.nome
        assert comprovante.conteudo_json["pis"] == employee_a.pis
        assert comprovante.conteudo_json["nsr"] == record.nsr
        assert comprovante.conteudo_json["tipo"] == record.tipo
        assert "data" in comprovante.conteudo_json
        assert "hora" in comprovante.conteudo_json


@pytest.mark.django_db(transaction=True)
def test_registrar_concorrente_gera_nsr_unico_e_sequencial(tenant_a):
    total = 20
    employees = []
    for idx in range(total):
        seq = f"{idx + 1:03d}"
        employees.append(
            Employee.all_objects.create(
                tenant=tenant_a,
                nome=f"Funcionario {seq}",
                cpf=f"70000000{seq}",
                pis=f"80000000{seq}",
                ativo=True,
            )
        )

    service = AttendanceService(biometria_service=FakeBiometriaService())

    def call_service(employee):
        close_old_connections()
        record, _ = service.registrar(
            employee=employee,
            tipo=AttendanceRecord.Tipo.ENTRADA,
            imagem_bytes=f"img-{employee.id}".encode(),
            timestamp=timezone.now(),
        )
        return record.nsr

    with ThreadPoolExecutor(max_workers=8) as executor:
        nsrs = list(executor.map(call_service, employees))

    assert sorted(nsrs) == list(range(1, total + 1))
    assert AttendanceRecord.all_objects.filter(tenant=tenant_a).count() == total


@pytest.mark.django_db
class TestAttendanceRegisterEndpoint:
    endpoint = "/api/attendance/register/"

    def test_registra_ponto_via_device_token(self, tenant_a, user_a, employee_a, monkeypatch):
        def fake_verify(self, employee, imagem_bytes):
            return {"autenticado": True, "distancia": 0.25, "threshold": 0.68}

        monkeypatch.setattr(
            "apps.attendance.services.BiometriaService.verificar",
            fake_verify,
        )

        _, device = _prepare_operational_clock(
            tenant=tenant_a,
            user=user_a,
            employee=employee_a,
            device=Device.objects.create(
                tenant=tenant_a,
                device_id="tablet-a",
                nome="Tablet A",
            ),
        )
        token = _device_access_token_for(
            user_a,
            tenant_a.id,
            device_id=device.device_id,
            device_pk=device.id,
        )
        client = APIClient()
        response = client.post(
            self.endpoint,
            data={
                "employee_id": employee_a.id,
                "tipo": AttendanceRecord.Tipo.ENTRADA,
                "imagem": _build_test_image_file(),
            },
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 201
        assert response.data["employee_id"] == employee_a.id
        assert response.data["tipo"] == AttendanceRecord.Tipo.ENTRADA
        assert response.data["nsr"] == 1

        record = AttendanceRecord.all_objects.get(id=response.data["id"])
        comprovante = Comprovante.all_objects.get(registro=record)
        assert comprovante.conteudo_json["nsr"] == record.nsr

    def test_bloqueia_token_nao_device(self, tenant_a, user_a, employee_a):
        client = APIClient()
        client.force_authenticate(user=user_a)

        response = client.post(
            self.endpoint,
            data={
                "employee_id": employee_a.id,
                "tipo": AttendanceRecord.Tipo.ENTRADA,
                "imagem": _build_test_image_file(),
            },
            format="multipart",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 403

    def test_bloqueia_funcionario_de_outro_tenant(self, tenant_a, user_a, employee_b):
        employee_owner = Employee.all_objects.create(
            tenant=tenant_a,
            nome="Funcionario Tenant A",
            cpf="55555555002",
            pis="55555555002",
            ativo=True,
        )
        _, device = _prepare_operational_clock(
            tenant=tenant_a,
            user=user_a,
            employee=employee_owner,
            device=Device.objects.create(
                tenant=tenant_a,
                device_id="tablet-a",
                nome="Tablet A",
            ),
        )
        token = _device_access_token_for(
            user_a,
            tenant_a.id,
            device_id=device.device_id,
            device_pk=device.id,
        )
        client = APIClient()

        response = client.post(
            self.endpoint,
            data={
                "employee_id": employee_b.id,
                "tipo": AttendanceRecord.Tipo.ENTRADA,
                "imagem": _build_test_image_file(),
            },
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 404

    def test_bloqueia_quando_colaborador_nao_esta_atribuido_ao_relogio(
        self, tenant_a, user_a, employee_a
    ):
        device = Device.objects.create(
            tenant=tenant_a,
            device_id="tablet-a",
            nome="Tablet A",
        )
        TimeClock.all_objects.create(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="CD34EF",
            current_device=device,
            status=TimeClock.Status.ATIVO,
        )
        FacialEmbedding.objects.create(
            employee=employee_a,
            embedding_data=b"embedding",
            ativo=True,
        )
        token = _device_access_token_for(
            user_a,
            tenant_a.id,
            device_id=device.device_id,
            device_pk=device.id,
        )
        client = APIClient()

        response = client.post(
            self.endpoint,
            data={
                "employee_id": employee_a.id,
                "tipo": AttendanceRecord.Tipo.ENTRADA,
                "imagem": _build_test_image_file(),
            },
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 400
        assert "Colaborador não está atribuído" in str(response.data)

    def test_bloqueia_quando_batida_esta_fora_da_cerca_virtual(
        self, tenant_a, user_a, employee_a, monkeypatch
    ):
        def fake_verify(self, employee, imagem_bytes):
            return {"autenticado": True, "distancia": 0.25, "threshold": 0.68}

        monkeypatch.setattr(
            "apps.attendance.services.BiometriaService.verificar",
            fake_verify,
        )
        time_clock, device = _prepare_operational_clock(
            tenant=tenant_a,
            user=user_a,
            employee=employee_a,
            device=Device.objects.create(
                tenant=tenant_a,
                device_id="tablet-a",
                nome="Tablet A",
            ),
        )
        TimeClockService().configure_geofence(
            time_clock=time_clock,
            latitude=-3.731861,
            longitude=-38.526670,
            raio_metros=50,
        )
        token = _device_access_token_for(
            user_a,
            tenant_a.id,
            device_id=device.device_id,
            device_pk=device.id,
        )
        client = APIClient()

        response = client.post(
            self.endpoint,
            data={
                "employee_id": employee_a.id,
                "tipo": AttendanceRecord.Tipo.ENTRADA,
                "imagem": _build_test_image_file(),
                "latitude": "-3.700000",
                "longitude": "-38.500000",
            },
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 400
        assert "Batida fora da cerca virtual" in str(response.data)


@pytest.mark.django_db
class TestAttendanceComprovanteEndpoint:
    def test_retorna_comprovante_do_registro(self, tenant_a, user_a, employee_a, monkeypatch):
        def fake_verify(self, employee, imagem_bytes):
            return {"autenticado": True, "distancia": 0.2, "threshold": 0.68}

        monkeypatch.setattr(
            "apps.attendance.services.BiometriaService.verificar",
            fake_verify,
        )

        time_clock, device = _prepare_operational_clock(
            tenant=tenant_a,
            user=user_a,
            employee=employee_a,
            device=Device.objects.create(
                tenant=tenant_a,
                device_id="tablet-a",
                nome="Tablet A",
            ),
        )
        record, _ = AttendanceService().registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.ENTRADA,
            imagem_bytes=b"img-comprovante",
            time_clock=time_clock,
        )

        token = _device_access_token_for(
            user_a,
            tenant_a.id,
            device_id=device.device_id,
            device_pk=device.id,
        )
        client = APIClient()
        response = client.get(
            f"/api/attendance/{record.id}/comprovante/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 200
        assert response.data["registro_id"] == record.id
        assert response.data["tenant_id"] == str(tenant_a.id)
        assert response.data["conteudo_json"]["nome"] == employee_a.nome
        assert response.data["conteudo_json"]["pis"] == employee_a.pis
        assert response.data["conteudo_json"]["nsr"] == record.nsr
        assert response.data["conteudo_json"]["tipo"] == record.tipo
        assert response.data["timestamp_carimbo"] is not None
        assert len(response.data["hash_carimbo"]) == 64

    def test_bloqueia_acesso_de_outro_tenant(self, tenant_a, tenant_b, user_a, employee_a, monkeypatch):
        user_b = User.objects.create_user(
            email="attendance@tenant-b.com",
            password="12345678",
            tenant=tenant_b,
            role=User.Role.ADMIN,
        )

        def fake_verify(self, employee, imagem_bytes):
            return {"autenticado": True, "distancia": 0.2, "threshold": 0.68}

        monkeypatch.setattr(
            "apps.attendance.services.BiometriaService.verificar",
            fake_verify,
        )

        time_clock, _ = _prepare_operational_clock(
            tenant=tenant_a,
            user=user_a,
            employee=employee_a,
        )
        record, _ = AttendanceService().registrar(
            employee=employee_a,
            tipo=AttendanceRecord.Tipo.ENTRADA,
            imagem_bytes=b"img-comprovante-tenant",
            time_clock=time_clock,
        )

        device_b = Device.objects.create(
            tenant=tenant_b,
            device_id="tablet-b",
            nome="Tablet B",
        )
        token_b = _device_access_token_for(
            user_b,
            tenant_b.id,
            device_id=device_b.device_id,
            device_pk=device_b.id,
        )
        client = APIClient()
        response = client.get(
            f"/api/attendance/{record.id}/comprovante/",
            HTTP_AUTHORIZATION=f"Bearer {token_b}",
            HTTP_HOST=f"{tenant_b.cnpj}.ponto.local",
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestTimeClockApiEndpoints:
    def test_ativacao_por_codigo_vincula_device_e_retorna_token(self, tenant_a, user_a):
        time_clock = TimeClock.all_objects.create(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="ZX12CV",
            status=TimeClock.Status.ATIVO,
        )
        client = APIClient()

        response = client.post(
            "/api/relogios/ativar/",
            data={
                "activation_code": "ZX12CV",
                "device_id": "android-tablet-portaria-01",
                "nome_dispositivo": "Tablet Portaria",
                "plataforma": "ANDROID",
            },
            format="json",
        )

        time_clock.refresh_from_db()
        assert response.status_code == 200
        assert response.data["device"]["device_id"] == "android-tablet-portaria-01"
        assert response.data["relogio"]["id"] == str(time_clock.id)
        assert response.data["relogio"]["status"] == TimeClock.Status.ATIVO
        assert time_clock.current_device is not None
        assert time_clock.current_device.device_id == "android-tablet-portaria-01"

    def test_ativacao_bloqueia_relogio_em_manutencao(self, tenant_a, user_a):
        TimeClock.all_objects.create(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="ZX34CV",
            status=TimeClock.Status.EM_MANUTENCAO,
        )
        client = APIClient()

        response = client.post(
            "/api/relogios/ativar/",
            data={
                "activation_code": "ZX34CV",
                "device_id": "android-tablet-portaria-02",
                "plataforma": "ANDROID",
            },
            format="json",
        )

        assert response.status_code == 409
        assert "Relógio indisponível" in str(response.data)

    def test_get_e_patch_detalhe_do_relogio(self, tenant_a, user_a):
        time_clock = TimeClock.all_objects.create(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="PL45OK",
            status=TimeClock.Status.ATIVO,
        )
        client = APIClient()
        client.force_authenticate(user=user_a)

        get_response = client.get(
            f"/api/relogios/{time_clock.id}/",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )
        patch_response = client.patch(
            f"/api/relogios/{time_clock.id}/",
            data={
                "nome": "Relogio Portaria Principal",
                "descricao": "Tablet principal",
                "status": "EM_MANUTENCAO",
            },
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        time_clock.refresh_from_db()
        assert get_response.status_code == 200
        assert get_response.data["codigo_ativacao"] == "PL45OK"
        assert get_response.data["cerca_virtual"] is None
        assert patch_response.status_code == 200
        assert time_clock.nome == "Relogio Portaria Principal"
        assert time_clock.status == TimeClock.Status.EM_MANUTENCAO

    def test_put_e_delete_cerca_virtual(self, tenant_a, user_a):
        time_clock = TimeClock.all_objects.create(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="GH56IJ",
            status=TimeClock.Status.ATIVO,
        )
        client = APIClient()
        client.force_authenticate(user=user_a)

        put_response = client.put(
            f"/api/relogios/{time_clock.id}/cerca-virtual/",
            data={
                "latitude": "-3.731861",
                "longitude": "-38.526670",
                "raio_metros": 120,
                "ativo": True,
            },
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )
        delete_response = client.delete(
            f"/api/relogios/{time_clock.id}/cerca-virtual/",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert put_response.status_code == 200
        assert put_response.data["raio_metros"] == 120
        assert delete_response.status_code == 204
        time_clock.refresh_from_db()
        assert time_clock.geofence.ativo is False

    def test_lista_e_move_colaboradores_via_api(self, tenant_a, user_a):
        time_clock = TimeClock.all_objects.create(
            tenant=tenant_a,
            created_by=user_a,
            nome="Relogio Portaria",
            activation_code="LM78NO",
            status=TimeClock.Status.ATIVO,
        )
        employee = Employee.all_objects.create(
            tenant=tenant_a,
            nome="Maria Lopes",
            cpf="55555555003",
            pis="55555555003",
            ativo=True,
        )
        client = APIClient()
        client.force_authenticate(user=user_a)

        available_response = client.get(
            f"/api/relogios/{time_clock.id}/colaboradores/disponiveis/",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )
        move_response = client.post(
            f"/api/relogios/{time_clock.id}/colaboradores/mover-selecionados/",
            data={"employee_ids": [employee.id]},
            format="json",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )
        assigned_response = client.get(
            f"/api/relogios/{time_clock.id}/colaboradores/no-relogio/",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert available_response.status_code == 200
        assert available_response.data["count"] == 1
        assert move_response.status_code == 200
        assert move_response.data["moved_count"] == 1
        assert assigned_response.status_code == 200
        assert assigned_response.data["count"] == 1


@pytest.mark.django_db
class TestAttendanceSyncEndpoint:
    endpoint = "/api/attendance/sync/"

    def test_sync_offline_com_idempotencia_e_nsr_no_servidor(
        self,
        tenant_a,
        user_a,
        employee_a,
        monkeypatch,
    ):
        def fake_verify(self, employee, imagem_bytes):
            return {"autenticado": True, "distancia": 0.2, "threshold": 0.68}

        monkeypatch.setattr(
            "apps.attendance.services.BiometriaService.verificar",
            fake_verify,
        )

        _, device = _prepare_operational_clock(
            tenant=tenant_a,
            user=user_a,
            employee=employee_a,
            device=Device.objects.create(
                tenant=tenant_a,
                device_id="tablet-a",
                nome="Tablet A",
            ),
        )
        token = _device_access_token_for(
            user_a,
            tenant_a.id,
            device_id=device.device_id,
            device_pk=device.id,
        )
        client = APIClient()
        payload = {
            "registros": [
                {
                    "employee_id": employee_a.id,
                    "tipo": AttendanceRecord.Tipo.ENTRADA,
                    "timestamp": "2026-03-07T08:00:00-03:00",
                    "client_event_id": "evt-1",
                    "imagem_base64": base64.b64encode(b"img-evt-1").decode("ascii"),
                },
                {
                    "employee_id": employee_a.id,
                    "tipo": AttendanceRecord.Tipo.SAIDA,
                    "timestamp": "2026-03-07T12:00:00-03:00",
                    "client_event_id": "evt-2",
                    "imagem_base64": base64.b64encode(b"img-evt-2").decode("ascii"),
                },
            ]
        }

        response = client.post(
            self.endpoint,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 200
        assert len(response.data["results"]) == 2
        assert response.data["results"][0]["created"] is True
        assert response.data["results"][1]["created"] is True
        assert response.data["results"][0]["record"]["nsr"] == 1
        assert response.data["results"][1]["record"]["nsr"] == 2
        assert response.data["results"][0]["record"]["origem"] == AttendanceRecord.Origem.OFFLINE
        assert response.data["results"][0]["record"]["sincronizado_em"] is not None

        assert AttendanceRecord.all_objects.filter(tenant=tenant_a).count() == 2
        assert Comprovante.all_objects.filter(tenant=tenant_a).count() == 2

        retry_response = client.post(
            self.endpoint,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert retry_response.status_code == 200
        assert retry_response.data["results"][0]["created"] is False
        assert retry_response.data["results"][1]["created"] is False
        assert AttendanceRecord.all_objects.filter(tenant=tenant_a).count() == 2

    def test_sync_rejeita_lote_fora_de_ordem(self, tenant_a, user_a, employee_a, monkeypatch):
        def fake_verify(self, employee, imagem_bytes):
            return {"autenticado": True, "distancia": 0.2, "threshold": 0.68}

        monkeypatch.setattr(
            "apps.attendance.services.BiometriaService.verificar",
            fake_verify,
        )

        _, device = _prepare_operational_clock(
            tenant=tenant_a,
            user=user_a,
            employee=employee_a,
            device=Device.objects.create(
                tenant=tenant_a,
                device_id="tablet-a",
                nome="Tablet A",
            ),
        )
        token = _device_access_token_for(
            user_a,
            tenant_a.id,
            device_id=device.device_id,
            device_pk=device.id,
        )
        client = APIClient()
        payload = {
            "registros": [
                {
                    "employee_id": employee_a.id,
                    "tipo": AttendanceRecord.Tipo.ENTRADA,
                    "timestamp": "2026-03-07T09:00:00-03:00",
                    "client_event_id": "evt-out-1",
                    "imagem_base64": base64.b64encode(b"img-out-1").decode("ascii"),
                },
                {
                    "employee_id": employee_a.id,
                    "tipo": AttendanceRecord.Tipo.SAIDA,
                    "timestamp": "2026-03-07T08:00:00-03:00",
                    "client_event_id": "evt-out-2",
                    "imagem_base64": base64.b64encode(b"img-out-2").decode("ascii"),
                },
            ]
        }

        response = client.post(
            self.endpoint,
            data=payload,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 400
        assert "ordem crescente de timestamp" in str(response.data)
