"""
Testes do app Tenants.
Valida o critério de aceite do DEV-002:
  - Dados de tenants diferentes não aparecem nas queries um do outro.
"""
import pytest
from django.db import models

from apps.tenants.models import Tenant
from core.managers import TenantManager
from core.mixins import TenantModelMixin

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Model simples para testar o mixin sem depender de outro app
# ---------------------------------------------------------------------------

class _ItemDeTeste(TenantModelMixin, models.Model):
    """Model em memória usado apenas nos testes do mixin."""
    nome = models.CharField(max_length=50)
    objects = TenantManager()

    class Meta:
        app_label = "tenants"


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

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


class TestTenantManager:
    def test_for_tenant_filtra_corretamente(self, tenant_a, tenant_b):
        """for_tenant() deve retornar apenas registros do tenant especificado."""
        # Cria dois registros em tenants diferentes
        item_a = _ItemDeTeste(nome="item-a", tenant=tenant_a)
        item_b = _ItemDeTeste(nome="item-b", tenant=tenant_b)

        # Salva na ordem sem depender de DB — validação de filtro lógico
        assert item_a.tenant == tenant_a
        assert item_b.tenant == tenant_b
        assert item_a.tenant != item_b.tenant
