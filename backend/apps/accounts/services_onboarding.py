"""Serviços de domínio para onboarding de conta e empresa."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenants.models import Tenant

from .models import User


class AccountOnboardingService:
    """Encapsula regras transacionais do onboarding owner->tenant."""

    @staticmethod
    @transaction.atomic
    def create_owner_account(
        *,
        first_name: str,
        last_name: str,
        email: str,
        cpf: str,
        phone: str,
        password: str,
    ) -> User:
        return User.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            cpf=cpf,
            phone=phone,
            email=email,
            password=password,
            role=User.Role.ADMIN,
            is_account_owner=True,
            is_active=True,
        )

    @staticmethod
    @transaction.atomic
    def upsert_company_for_owner(
        *,
        owner: User,
        company_data: dict,
        existing_tenant: Tenant | None = None,
    ) -> Tenant:
        locked_owner = User.objects.select_for_update().get(pk=owner.pk)
        if locked_owner.tenant_id and (
            not existing_tenant or locked_owner.tenant_id != existing_tenant.pk
        ):
            raise ValidationError("Esta conta já possui empresa vinculada.")

        tipo_pessoa = company_data["tipo_pessoa"]
        documento = company_data["documento"]

        tenant = existing_tenant or Tenant()
        tenant.tipo_pessoa = tipo_pessoa
        tenant.documento = documento
        tenant.cnpj = documento if tipo_pessoa == Tenant.TipoPessoa.PJ else None
        tenant.razao_social = company_data["razao_social"]
        tenant.nome_fantasia = company_data["nome_fantasia"]
        tenant.email_contato = company_data["email_contato"]
        tenant.telefone_contato = company_data["telefone_contato"]
        tenant.cep = company_data["cep"]
        tenant.logradouro = company_data["logradouro"]
        tenant.numero = company_data["numero"]
        tenant.complemento = company_data["complemento"]
        tenant.bairro = company_data["bairro"]
        tenant.cidade = company_data["cidade"]
        tenant.estado = company_data["estado"]
        tenant.responsavel_nome = company_data["responsavel_nome"]
        tenant.responsavel_cpf = company_data["responsavel_cpf"]
        tenant.responsavel_cargo = company_data["responsavel_cargo"]
        tenant.logo_url = company_data["logo_url"]
        tenant.website = company_data["website"]
        tenant.cno_caepf = company_data["cno_caepf"]
        tenant.inscricao_estadual = company_data["inscricao_estadual"]
        tenant.inscricao_municipal = company_data["inscricao_municipal"]
        tenant.onboarding_step = max(2, int(tenant.onboarding_step or 2))
        tenant.save()

        locked_owner.tenant = tenant
        locked_owner.is_account_owner = True
        locked_owner.save(update_fields=["tenant", "is_account_owner"])

        # Sincroniza objeto em memória para o restante do fluxo da request.
        owner.tenant = tenant
        owner.is_account_owner = True
        return tenant
