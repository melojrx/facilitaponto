"""Forms do domínio de funcionários."""

import json

from django import forms
from django.core.exceptions import ValidationError

from .journey_config import (
    normalize_12x36_config,
    normalize_externa_config,
    normalize_fracionada_config,
    normalize_semanal_config,
    parse_json_payload,
)
from .models import Employee, WorkSchedule
from .services import EmployeeRegistrationService


class WorkScheduleForm(forms.Form):
    SEMANAL_SUBTIPO_CHOICES = (
        ("PERSONALIZAR", "Personalizar"),
        ("INTEGRAL_44H", "Integral 44h"),
        ("COMERCIAL_40H", "Comercial 40h"),
        ("PARCIAL_30H", "Parcial 30h"),
    )

    nome = forms.CharField(
        label="Nome da Jornada",
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Jornada Padrão 44h"}),
    )
    descricao = forms.CharField(
        label="Descrição",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Descrição opcional da jornada", "rows": 3}),
    )
    tipo = forms.ChoiceField(
        label="Tipo de Jornada",
        choices=WorkSchedule.TipoJornada.choices,
    )
    semanal_subtipo = forms.ChoiceField(
        label="Modelo semanal",
        choices=SEMANAL_SUBTIPO_CHOICES,
        required=False,
    )
    semanal_intervalo_reduzido = forms.BooleanField(
        label="Intervalo reduzido por convenção coletiva",
        required=False,
    )
    semanal_norma_coletiva_ref = forms.CharField(
        label="Referência da norma coletiva",
        max_length=120,
        required=False,
    )
    semanal_dias_json = forms.CharField(
        label="Configuração semanal (JSON)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 8}),
    )
    x12x36_data_inicio_escala = forms.DateField(
        label="Data de início da escala",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    x12x36_horario_entrada = forms.TimeField(
        label="Horário de entrada",
        required=False,
        input_formats=["%H:%M"],
        widget=forms.TimeInput(attrs={"type": "time"}),
    )
    fracionada_intervalo_reduzido = forms.BooleanField(
        label="Intervalo reduzido por convenção coletiva",
        required=False,
    )
    fracionada_norma_coletiva_ref = forms.CharField(
        label="Referência da norma coletiva",
        max_length=120,
        required=False,
    )
    fracionada_dias_json = forms.CharField(
        label="Configuração fracionada (JSON)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant")
        self.instance = kwargs.pop("instance", None)
        if self.instance and not args and "initial" not in kwargs:
            kwargs["initial"] = self.initial_from_schedule(self.instance)
        super().__init__(*args, **kwargs)

    @staticmethod
    def initial_from_schedule(schedule: WorkSchedule) -> dict:
        configuracao = schedule.configuracao or {}
        initial = {
            "nome": schedule.nome,
            "descricao": schedule.descricao,
            "tipo": schedule.tipo,
        }

        if schedule.tipo == WorkSchedule.TipoJornada.SEMANAL:
            initial.update(
                {
                    "semanal_subtipo": configuracao.get("subtipo", "PERSONALIZAR"),
                    "semanal_intervalo_reduzido": bool(
                        configuracao.get("intervalo_reduzido_convencao", False)
                    ),
                    "semanal_norma_coletiva_ref": configuracao.get("norma_coletiva_ref", ""),
                    "semanal_dias_json": json.dumps(configuracao.get("dias", [])),
                }
            )
        elif schedule.tipo == WorkSchedule.TipoJornada.X12X36:
            initial.update(
                {
                    "x12x36_data_inicio_escala": configuracao.get("data_inicio_escala", ""),
                    "x12x36_horario_entrada": configuracao.get("horario_entrada", ""),
                }
            )
        elif schedule.tipo == WorkSchedule.TipoJornada.FRACIONADA:
            initial.update(
                {
                    "fracionada_intervalo_reduzido": bool(
                        configuracao.get("intervalo_reduzido_convencao", False)
                    ),
                    "fracionada_norma_coletiva_ref": configuracao.get("norma_coletiva_ref", ""),
                    "fracionada_dias_json": json.dumps(configuracao.get("dias", [])),
                }
            )

        return initial

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if len(nome) < 3:
            raise forms.ValidationError("O nome da jornada deve ter pelo menos 3 caracteres.")
        duplicado_qs = WorkSchedule.all_objects.filter(
            tenant=self.tenant,
            nome__iexact=nome,
            ativo=True,
        )
        if self.instance:
            duplicado_qs = duplicado_qs.exclude(pk=self.instance.pk)
        duplicado = duplicado_qs.exists()
        if duplicado:
            raise forms.ValidationError("Já existe uma jornada com este nome na sua empresa.")
        return nome

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")

        if not tipo:
            return cleaned_data

        try:
            if tipo == WorkSchedule.TipoJornada.SEMANAL:
                dias_payload = parse_json_payload(
                    cleaned_data.get("semanal_dias_json"),
                    field_label="jornada semanal",
                )
                cleaned_data["configuracao"] = normalize_semanal_config(
                    subtipo=cleaned_data.get("semanal_subtipo") or "PERSONALIZAR",
                    intervalo_reduzido_convencao=cleaned_data.get("semanal_intervalo_reduzido", False),
                    norma_coletiva_ref=cleaned_data.get("semanal_norma_coletiva_ref", ""),
                    dias_payload=dias_payload,
                )
            elif tipo == WorkSchedule.TipoJornada.X12X36:
                cleaned_data["configuracao"] = normalize_12x36_config(
                    data_inicio_escala=cleaned_data.get("x12x36_data_inicio_escala"),
                    horario_entrada=cleaned_data.get("x12x36_horario_entrada"),
                )
            elif tipo == WorkSchedule.TipoJornada.FRACIONADA:
                dias_payload = parse_json_payload(
                    cleaned_data.get("fracionada_dias_json"),
                    field_label="jornada fracionada",
                )
                cleaned_data["configuracao"] = normalize_fracionada_config(
                    intervalo_reduzido_convencao=cleaned_data.get("fracionada_intervalo_reduzido", False),
                    norma_coletiva_ref=cleaned_data.get("fracionada_norma_coletiva_ref", ""),
                    dias_payload=dias_payload,
                )
            elif tipo == WorkSchedule.TipoJornada.EXTERNA:
                raw_externa_config = {
                    "semanal_dias_json": cleaned_data.get("semanal_dias_json"),
                    "x12x36_data_inicio_escala": cleaned_data.get("x12x36_data_inicio_escala"),
                    "x12x36_horario_entrada": cleaned_data.get("x12x36_horario_entrada"),
                    "fracionada_dias_json": cleaned_data.get("fracionada_dias_json"),
                }
                has_extra_payload = any(str(value or "").strip() for value in raw_externa_config.values())
                cleaned_data["configuracao"] = normalize_externa_config(
                    raw_externa_config if has_extra_payload else {}
                )
            else:
                self.add_error("tipo", "Tipo de jornada inválido.")
        except ValidationError as exc:
            self.add_error("tipo", exc.messages[0] if exc.messages else str(exc))

        return cleaned_data

    def save(self) -> WorkSchedule:
        if self.instance:
            self.instance.nome = self.cleaned_data["nome"]
            self.instance.descricao = self.cleaned_data["descricao"]
            self.instance.tipo = self.cleaned_data["tipo"]
            self.instance.configuracao = self.cleaned_data.get("configuracao", {})
            self.instance.save(update_fields=["nome", "descricao", "tipo", "configuracao"])
            return self.instance

        return WorkSchedule.all_objects.create(
            tenant=self.tenant,
            nome=self.cleaned_data["nome"],
            descricao=self.cleaned_data["descricao"],
            tipo=self.cleaned_data["tipo"],
            configuracao=self.cleaned_data.get("configuracao", {}),
        )


class EmployeeRegistrationForm(forms.Form):
    nome = forms.CharField(
        label="Nome Completo",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Maria Clara Santos"}),
    )
    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        widget=forms.TextInput(attrs={"placeholder": "000.000.000-00"}),
    )
    pis = forms.CharField(
        label="PIS/PASEP",
        max_length=14,
        widget=forms.TextInput(attrs={"placeholder": "000.00000.00-0"}),
    )
    data_nascimento = forms.DateField(
        label="Data de Nascimento",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    email = forms.EmailField(
        label="E-mail",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "colaborador@empresa.com"}),
    )
    telefone = forms.CharField(
        label="Telefone",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
    )
    funcao = forms.CharField(
        label="Funcao/Cargo",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Analista de RH"}),
    )
    departamento = forms.CharField(
        label="Departamento/Setor",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex: Operacoes"}),
    )
    data_admissao = forms.DateField(
        label="Data de Admissao",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    matricula_interna = forms.CharField(
        label="Matricula Interna",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex: COL-001"}),
    )
    work_schedule = forms.ModelChoiceField(
        label="Selecionar Jornada",
        queryset=WorkSchedule.all_objects.none(),
        empty_label="Selecione uma jornada",
    )

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant")
        self.instance = kwargs.pop("instance", None)
        if self.instance and not args and "initial" not in kwargs:
            kwargs["initial"] = self.initial_from_employee(self.instance)
        super().__init__(*args, **kwargs)
        self.fields["work_schedule"].queryset = WorkSchedule.all_objects.filter(
            tenant=self.tenant,
            ativo=True,
        ).order_by("nome")

    @staticmethod
    def initial_from_employee(employee: Employee) -> dict:
        return {
            "nome": employee.nome,
            "cpf": employee.cpf,
            "pis": employee.pis,
            "data_nascimento": employee.data_nascimento,
            "email": employee.email,
            "telefone": employee.telefone,
            "funcao": employee.funcao,
            "departamento": employee.departamento,
            "data_admissao": employee.data_admissao,
            "matricula_interna": employee.matricula_interna,
            "work_schedule": employee.work_schedule_id,
        }

    def save(self) -> Employee | None:
        try:
            payload = {
                "nome": self.cleaned_data["nome"],
                "cpf": self.cleaned_data["cpf"],
                "pis": self.cleaned_data["pis"],
                "work_schedule_id": self.cleaned_data["work_schedule"].id,
                "email": self.cleaned_data.get("email", ""),
                "telefone": self.cleaned_data.get("telefone", ""),
                "data_nascimento": self.cleaned_data.get("data_nascimento"),
                "funcao": self.cleaned_data.get("funcao", ""),
                "departamento": self.cleaned_data.get("departamento", ""),
                "data_admissao": self.cleaned_data.get("data_admissao"),
                "matricula_interna": self.cleaned_data.get("matricula_interna", ""),
                "ativo": self.instance.ativo if self.instance else True,
            }
            if self.instance:
                return EmployeeRegistrationService.update_employee(
                    employee=self.instance,
                    **payload,
                )
            return EmployeeRegistrationService.create_employee(
                tenant=self.tenant,
                **payload,
            )
        except ValidationError as exc:
            self._apply_service_errors(exc)
            return None

    def _apply_service_errors(self, exc: ValidationError):
        if hasattr(exc, "message_dict"):
            for field, messages in exc.message_dict.items():
                target_field = field if field in self.fields else None
                for message in messages:
                    self.add_error(target_field, message)
            return

        for message in exc.messages:
            self.add_error(None, message)
