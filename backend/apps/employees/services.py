from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Employee, NSRSequence, WorkSchedule
from .validators import (
    normalize_optional_email,
    normalize_optional_phone,
    normalize_optional_text,
)


def get_next_nsr(tenant_id):
    """
    Gera próximo NSR de forma atômica por tenant.

    O lock pessimista (`select_for_update`) impede colisão em requests concorrentes.
    """
    with transaction.atomic():
        sequence, _ = NSRSequence.all_objects.select_for_update().get_or_create(
            tenant_id=tenant_id,
            defaults={"ultimo_nsr": 0},
        )
        sequence.ultimo_nsr += 1
        sequence.save(update_fields=["ultimo_nsr", "updated_at"])
        return sequence.ultimo_nsr


class EmployeeRegistrationService:
    """Servico transacional para cadastro operacional de colaboradores."""

    @classmethod
    @transaction.atomic
    def create_employee(
        cls,
        *,
        tenant,
        nome,
        cpf,
        pis,
        work_schedule_id,
        email="",
        telefone="",
        data_nascimento=None,
        funcao="",
        departamento="",
        data_admissao=None,
        matricula_interna="",
        ativo=True,
    ):
        schedule = cls._resolve_schedule(tenant=tenant, work_schedule_id=work_schedule_id)
        employee = Employee(
            tenant=tenant,
            nome=nome,
            cpf=cpf,
            pis=pis,
            email=normalize_optional_email(email),
            telefone=normalize_optional_phone(telefone),
            data_nascimento=data_nascimento,
            funcao=normalize_optional_text(funcao),
            departamento=normalize_optional_text(departamento),
            data_admissao=data_admissao,
            matricula_interna=normalize_optional_text(matricula_interna),
            work_schedule=schedule,
            ativo=ativo,
        )
        employee.full_clean()
        employee.save()
        return employee

    @classmethod
    @transaction.atomic
    def update_employee(
        cls,
        *,
        employee,
        nome,
        cpf,
        pis,
        work_schedule_id,
        email="",
        telefone="",
        data_nascimento=None,
        funcao="",
        departamento="",
        data_admissao=None,
        matricula_interna="",
        ativo=True,
    ):
        schedule = cls._resolve_schedule(tenant=employee.tenant, work_schedule_id=work_schedule_id)
        employee.nome = nome
        employee.cpf = cpf
        employee.pis = pis
        employee.email = normalize_optional_email(email)
        employee.telefone = normalize_optional_phone(telefone)
        employee.data_nascimento = data_nascimento
        employee.funcao = normalize_optional_text(funcao)
        employee.departamento = normalize_optional_text(departamento)
        employee.data_admissao = data_admissao
        employee.matricula_interna = normalize_optional_text(matricula_interna)
        employee.work_schedule = schedule
        employee.ativo = ativo
        employee.full_clean()
        employee.save()
        return employee

    @classmethod
    @transaction.atomic
    def update_employee_status(cls, *, employee, ativo):
        employee.ativo = ativo
        employee.full_clean()
        employee.save(update_fields=["ativo"])
        return employee

    @staticmethod
    def _resolve_schedule(*, tenant, work_schedule_id):
        if not work_schedule_id:
            return None
        try:
            return WorkSchedule.all_objects.get(id=work_schedule_id, tenant=tenant, ativo=True)
        except WorkSchedule.DoesNotExist as exc:
            raise ValidationError(
                {"work_schedule": "Selecione uma jornada valida da sua empresa."}
            ) from exc
