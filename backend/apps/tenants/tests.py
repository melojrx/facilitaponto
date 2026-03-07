"""
Testes do app Tenants.
Valida o critério de aceite do DEV-002:
  - Dados de tenants diferentes não aparecem nas queries um do outro.
"""
import pytest
from django.db import connection, models
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.models import Tenant
from core.managers import TenantManager
from core.middleware import TenantMiddleware
from core.mixins import TenantModelMixin
from core.tenant_context import tenant_context


@pytest.fixture
def tenant_a(db):
    return Tenant.objects.create(
        cnpj="00000000000101",
        razao_social="Empresa A Ltda",
        plano=Tenant.Plano.BASICO,
    )


@pytest.fixture
def tenant_b(db):
    return Tenant.objects.create(
        cnpj="00000000000202",
        razao_social="Empresa B S/A",
        plano=Tenant.Plano.PROFISSIONAL,
    )


class _ItemDeTeste(TenantModelMixin, models.Model):
    """Model temporário para validar isolamento automático em queries reais."""

    nome = models.CharField(max_length=50)

    # Reforça explicitamente o contrato esperado do DEV-002
    objects = TenantManager()
    all_objects = TenantManager(scoped=False)

    class Meta:
        app_label = "tenants"
        db_table = "tenants_item_de_teste"


@pytest.fixture(scope="module", autouse=True)
def item_de_teste_table(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        with connection.schema_editor() as schema_editor:
            existing_tables = connection.introspection.table_names()
            if _ItemDeTeste._meta.db_table not in existing_tables:
                schema_editor.create_model(_ItemDeTeste)

        yield

        with connection.schema_editor() as schema_editor:
            existing_tables = connection.introspection.table_names()
            if _ItemDeTeste._meta.db_table in existing_tables:
                schema_editor.delete_model(_ItemDeTeste)


@pytest.mark.django_db
class TestTenantModel:
    def test_criacao(self, tenant_a):
        assert Tenant.objects.filter(cnpj="00000000000101").exists()

    def test_str(self, tenant_a):
        assert "Empresa A" in str(tenant_a)

    def test_id_e_uuid(self, tenant_a):
        import uuid

        assert isinstance(tenant_a.id, uuid.UUID)

    def test_ativo_por_padrao(self, tenant_a):
        assert tenant_a.ativo is True


@pytest.mark.django_db
class TestTenantManager:
    def test_sem_tenant_no_contexto_retorna_vazio_por_seguranca(self, tenant_a):
        _ItemDeTeste.all_objects.create(nome="item-a", tenant=tenant_a)

        assert _ItemDeTeste.objects.count() == 0

    def test_for_tenant_filtra_corretamente(self, tenant_a, tenant_b):
        _ItemDeTeste.all_objects.create(nome="item-a", tenant=tenant_a)
        _ItemDeTeste.all_objects.create(nome="item-b", tenant=tenant_b)

        nomes_a = list(
            _ItemDeTeste.objects.for_tenant(tenant_a).values_list("nome", flat=True)
        )
        nomes_b = list(
            _ItemDeTeste.objects.for_tenant(tenant_b).values_list("nome", flat=True)
        )

        assert nomes_a == ["item-a"]
        assert nomes_b == ["item-b"]

    def test_objects_usa_tenant_do_contexto_automaticamente(self, tenant_a, tenant_b):
        _ItemDeTeste.all_objects.create(nome="item-a", tenant=tenant_a)
        _ItemDeTeste.all_objects.create(nome="item-b", tenant=tenant_b)

        with tenant_context(tenant_a):
            nomes = list(_ItemDeTeste.objects.values_list("nome", flat=True))
            assert nomes == ["item-a"]

        with tenant_context(tenant_b):
            nomes = list(_ItemDeTeste.objects.values_list("nome", flat=True))
            assert nomes == ["item-b"]


@pytest.mark.django_db
class TestTenantMiddleware:
    def test_resolve_tenant_por_jwt(self, tenant_a):
        request_factory = RequestFactory()
        token = AccessToken()
        token["tenant_id"] = str(tenant_a.id)

        captured = {}

        def get_response(request):
            captured["tenant"] = request.tenant
            return HttpResponse("ok")

        middleware = TenantMiddleware(get_response)
        request = request_factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        response = middleware(request)

        assert response.status_code == 200
        assert captured["tenant"] == tenant_a

    def test_resolve_tenant_por_subdominio_cnpj(self, tenant_a):
        request_factory = RequestFactory()
        captured = {}

        def get_response(request):
            captured["tenant"] = request.tenant
            return HttpResponse("ok")

        middleware = TenantMiddleware(get_response)
        request = request_factory.get("/", HTTP_HOST=f"{tenant_a.cnpj}.ponto.local")

        response = middleware(request)

        assert response.status_code == 200
        assert captured["tenant"] == tenant_a

    def test_contexto_e_limpo_ao_final_do_request(self, tenant_a):
        request_factory = RequestFactory()
        token = AccessToken()
        token["tenant_id"] = str(tenant_a.id)

        def get_response(request):
            assert request.tenant == tenant_a
            return HttpResponse("ok")

        middleware = TenantMiddleware(get_response)
        request = request_factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        response = middleware(request)

        assert response.status_code == 200
        assert _ItemDeTeste.objects.count() == 0
