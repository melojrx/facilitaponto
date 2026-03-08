from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Cria (ou vincula) empresa seed para um usuário owner."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="jrmeloafrf@gmail.com",
            help="E-mail do usuário owner a ser vinculado na empresa seed.",
        )
        parser.add_argument(
            "--razao-social",
            default="FacilitaPonto Demo LTDA",
            help="Razão social da empresa seed.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        razao_social = options["razao_social"].strip()

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError(f"Usuário não encontrado para o e-mail: {email}")

        if user.tenant_id:
            if not user.is_account_owner:
                user.is_account_owner = True
                user.save(update_fields=["is_account_owner"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuário já vinculado à empresa '{user.tenant.razao_social}' ({user.tenant_id})."
                )
            )
            return

        tenant = None
        candidates = Tenant.objects.filter(email_contato__iexact=email)
        if user.cpf:
            candidates = candidates | Tenant.objects.filter(
                Q(documento=user.cpf) | Q(cnpj=user.cpf) | Q(responsavel_cpf=user.cpf)
            )
        candidates = candidates.distinct()

        if candidates.count() == 1:
            tenant = candidates.first()
        elif candidates.count() > 1:
            raise CommandError(
                "Foram encontradas múltiplas empresas candidatas para esse usuário. "
                "Vínculo manual necessário."
            )

        if tenant is None:
            documento = self._next_available_document()
            tenant = Tenant.objects.create(
                tipo_pessoa=Tenant.TipoPessoa.PJ,
                documento=documento,
                cnpj=documento,
                razao_social=razao_social,
                nome_fantasia="FacilitaPonto Demo",
                email_contato=email,
                telefone_contato=user.phone or "85999990000",
                responsavel_nome=f"{user.first_name} {user.last_name}".strip(),
                responsavel_cpf=user.cpf or "",
                onboarding_step=2,
            )
            self.stdout.write(self.style.WARNING(f"Empresa seed criada: {tenant.razao_social} ({tenant.id})"))
        else:
            self.stdout.write(self.style.WARNING(f"Empresa existente encontrada: {tenant.razao_social} ({tenant.id})"))

        user.tenant = tenant
        user.is_account_owner = True
        user.save(update_fields=["tenant", "is_account_owner"])
        self.stdout.write(self.style.SUCCESS(f"Vínculo concluído para {user.email} -> {tenant.razao_social}"))

    @staticmethod
    def _next_available_document():
        base_value = 11222333000181
        for offset in range(500):
            candidate = f"{base_value + offset:014d}"
            exists = Tenant.objects.filter(Q(documento=candidate) | Q(cnpj=candidate)).exists()
            if not exists:
                return candidate
        raise CommandError("Não foi possível gerar documento único para empresa seed.")
