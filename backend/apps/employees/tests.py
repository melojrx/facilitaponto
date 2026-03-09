from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.serializers import TenantTokenObtainPairSerializer
from apps.employees.models import Employee, NSRSequence, WorkSchedule
from apps.employees.services import get_next_nsr
from apps.tenants.models import Tenant
from core.tenant_context import tenant_context


@pytest.fixture
def tenant_a(db):
    return Tenant.objects.create(
        cnpj="33333333000133",
        razao_social="Tenant A Employees",
        plano=Tenant.Plano.BASICO,
    )


@pytest.fixture
def tenant_b(db):
    return Tenant.objects.create(
        cnpj="44444444000144",
        razao_social="Tenant B Employees",
        plano=Tenant.Plano.PROFISSIONAL,
    )


@pytest.fixture
def user_a(db, tenant_a):
    return User.objects.create_user(
        email="sync@tenant-a.com",
        password="12345678",
        tenant=tenant_a,
        role=User.Role.ADMIN,
    )


@pytest.fixture
def user_b(db, tenant_b):
    return User.objects.create_user(
        email="sync@tenant-b.com",
        password="12345678",
        tenant=tenant_b,
        role=User.Role.ADMIN,
    )


def _device_access_token_for(user, tenant_id, device_id="tablet-main"):
    refresh = RefreshToken.for_user(user)
    refresh["tenant_id"] = str(tenant_id)
    refresh["role"] = "device"
    refresh["is_device"] = True
    refresh["device_id"] = device_id
    return str(refresh.access_token)


@pytest.mark.django_db
class TestEmployeeModel:
    def test_cpf_unico_por_tenant(self, tenant_a, tenant_b):
        Employee.all_objects.create(
            tenant=tenant_a,
            nome="Maria A",
            cpf="12345678901",
            pis="11111111111",
            email="maria.a@empresa.com",
            ativo=True,
        )

        # Mesmo CPF em tenant diferente é permitido
        employee = Employee.all_objects.create(
            tenant=tenant_b,
            nome="Maria B",
            cpf="12345678901",
            pis="22222222222",
            email="maria.b@empresa.com",
            ativo=True,
        )

        assert employee.tenant == tenant_b

    def test_pis_deve_ter_11_digitos(self, tenant_a):
        employee = Employee(
            tenant=tenant_a,
            nome="João",
            cpf="99999999999",
            pis="123",  # inválido
            email="joao@empresa.com",
            ativo=True,
        )

        with pytest.raises(ValidationError):
            employee.full_clean()


@pytest.mark.django_db
class TestNSRService:
    def test_get_next_nsr_sequencial_por_tenant(self, tenant_a, tenant_b):
        assert get_next_nsr(tenant_a.id) == 1
        assert get_next_nsr(tenant_a.id) == 2
        assert get_next_nsr(tenant_b.id) == 1

        seq_a = NSRSequence.all_objects.get(tenant=tenant_a)
        seq_b = NSRSequence.all_objects.get(tenant=tenant_b)

        assert seq_a.ultimo_nsr == 2
        assert seq_b.ultimo_nsr == 1

    @pytest.mark.django_db(transaction=True)
    def test_get_next_nsr_concorrente_sem_colisao(self, tenant_a):
        total = 20

        def call_service(_):
            close_old_connections()
            return get_next_nsr(tenant_a.id)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(call_service, range(total)))

        assert sorted(results) == list(range(1, total + 1))
        assert NSRSequence.all_objects.get(tenant=tenant_a).ultimo_nsr == total


@pytest.mark.django_db
class TestActiveEmployeesEndpoint:
    endpoint = "/api/employees/active/"

    def test_lista_apenas_ativos_do_tenant_do_device(self, tenant_a, tenant_b, user_a, user_b):
        Employee.all_objects.create(
            tenant=tenant_a,
            nome="Ativo A",
            cpf="10000000001",
            pis="10000000001",
            ativo=True,
        )
        Employee.all_objects.create(
            tenant=tenant_a,
            nome="Inativo A",
            cpf="10000000002",
            pis="10000000002",
            ativo=False,
        )
        Employee.all_objects.create(
            tenant=tenant_b,
            nome="Ativo B",
            cpf="20000000001",
            pis="20000000001",
            ativo=True,
        )

        token_a = _device_access_token_for(user_a, tenant_a.id, device_id="tablet-a")
        client = APIClient()

        response = client.get(
            self.endpoint,
            HTTP_AUTHORIZATION=f"Bearer {token_a}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 200

        results = response.data["results"]
        assert len(results) == 1
        assert results[0]["nome"] == "Ativo A"

        token_b = _device_access_token_for(user_b, tenant_b.id, device_id="tablet-b")
        response_b = client.get(
            self.endpoint,
            HTTP_AUTHORIZATION=f"Bearer {token_b}",
            HTTP_HOST=f"{tenant_b.cnpj}.ponto.local",
        )

        assert response_b.status_code == 200
        assert response_b.data["results"][0]["nome"] == "Ativo B"

    def test_bloqueia_token_que_nao_e_de_device(self, tenant_a, user_a):
        Employee.all_objects.create(
            tenant=tenant_a,
            nome="Ativo A",
            cpf="30000000001",
            pis="30000000001",
            ativo=True,
        )

        user_token = TenantTokenObtainPairSerializer.get_token(user_a)
        access = str(user_token.access_token)

        client = APIClient()
        response = client.get(
            self.endpoint,
            HTTP_AUTHORIZATION=f"Bearer {access}",
            HTTP_HOST=f"{tenant_a.cnpj}.ponto.local",
        )

        assert response.status_code == 403

    def test_employee_objects_reflete_tenant_context(self, tenant_a, tenant_b):
        Employee.all_objects.create(
            tenant=tenant_a,
            nome="Contexto A",
            cpf="40000000001",
            pis="40000000001",
            ativo=True,
        )
        Employee.all_objects.create(
            tenant=tenant_b,
            nome="Contexto B",
            cpf="50000000001",
            pis="50000000001",
            ativo=True,
        )

        with tenant_context(tenant_a):
            assert list(Employee.objects.values_list("nome", flat=True)) == ["Contexto A"]

        with tenant_context(tenant_b):
            assert list(Employee.objects.values_list("nome", flat=True)) == ["Contexto B"]


@pytest.mark.django_db
class TestWorkScheduleModel:
    def test_cria_jornada_com_sucesso(self, tenant_a):
        schedule = WorkSchedule.all_objects.create(
            tenant=tenant_a,
            nome="Jornada Comercial",
            tipo=WorkSchedule.TipoJornada.SEMANAL,
        )
        assert schedule.pk is not None
        assert schedule.ativo is True

    def test_nome_duplicado_no_mesmo_tenant_levanta_erro(self, tenant_a):
        WorkSchedule.all_objects.create(
            tenant=tenant_a,
            nome="Jornada Duplicada",
            tipo=WorkSchedule.TipoJornada.SEMANAL,
        )
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            WorkSchedule.all_objects.create(
                tenant=tenant_a,
                nome="Jornada Duplicada",
                tipo=WorkSchedule.TipoJornada.X12X36,
            )

    def test_mesmo_nome_em_tenants_diferentes_e_permitido(self, tenant_a, tenant_b):
        WorkSchedule.all_objects.create(
            tenant=tenant_a,
            nome="Jornada Padrão",
            tipo=WorkSchedule.TipoJornada.SEMANAL,
        )
        schedule_b = WorkSchedule.all_objects.create(
            tenant=tenant_b,
            nome="Jornada Padrão",
            tipo=WorkSchedule.TipoJornada.FRACIONADA,
        )
        assert schedule_b.tenant == tenant_b

    def test_str_retorna_nome_e_tipo(self, tenant_a):
        schedule = WorkSchedule.all_objects.create(
            tenant=tenant_a,
            nome="Escala Saúde",
            tipo=WorkSchedule.TipoJornada.X12X36,
        )
        assert "Escala Saúde" in str(schedule)
        assert "12X36" in str(schedule)
