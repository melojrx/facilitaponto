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
from .models import WorkSchedule


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
