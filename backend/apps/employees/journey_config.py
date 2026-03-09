"""Valida e normaliza configurações de jornada por tipo."""

import json
from datetime import date, datetime, time, timedelta

from django.core.exceptions import ValidationError

WEEK_DAYS = [
    "SEGUNDA",
    "TERCA",
    "QUARTA",
    "QUINTA",
    "SEXTA",
    "SABADO",
    "DOMINGO",
]

SEMANAL_SUBTIPOS = {
    "INTEGRAL_44H",
    "COMERCIAL_40H",
    "PARCIAL_30H",
    "PERSONALIZAR",
}


def parse_json_payload(raw_value: str, *, field_label: str):
    value = (raw_value or "").strip()
    if not value:
        raise ValidationError(f"Informe a configuração de {field_label}.")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Configuração de {field_label} em JSON inválido.") from exc


def _to_hhmm(value, *, field_label: str):
    if value in (None, ""):
        return None

    if isinstance(value, time):
        return value.strftime("%H:%M")

    if not isinstance(value, str):
        raise ValidationError(f"{field_label} inválido.")

    value = value.strip()
    try:
        parsed = datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValidationError(f"{field_label} inválido. Use HH:MM.") from exc
    return parsed.strftime("%H:%M")


def _to_minutes(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 60 + int(minute)


def _minutes_to_hhmm(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def _add_hours_to_hhmm(hhmm: str, hours: int) -> tuple[str, bool]:
    total = _to_minutes(hhmm) + (hours * 60)
    wrapped = total >= (24 * 60)
    wrapped_minutes = total % (24 * 60)
    return _minutes_to_hhmm(wrapped_minutes), wrapped


def _js_weekday_index(value: date) -> int:
    # Monday=0 ... Sunday=6
    return value.weekday()


def _build_12x36_weekly_scale(*, data_inicio_escala: date, horario_entrada: str, horario_saida: str):
    week_start = data_inicio_escala - timedelta(days=_js_weekday_index(data_inicio_escala))
    saida_no_dia_seguinte = _to_minutes(horario_saida) <= _to_minutes(horario_entrada)
    escala = []
    total_minutes = 0

    for offset, day_key in enumerate(WEEK_DAYS):
        current_date = week_start + timedelta(days=offset)
        day_delta = (current_date - data_inicio_escala).days
        is_work_day = (day_delta % 2) == 0

        if is_work_day:
            total_minutes += 12 * 60
            escala.append(
                {
                    "data": current_date.isoformat(),
                    "dia_semana": day_key,
                    "tipo_dia": "TRABALHO",
                    "entrada": horario_entrada,
                    "saida": horario_saida,
                    "saida_no_dia_seguinte": saida_no_dia_seguinte,
                }
            )
        else:
            escala.append(
                {
                    "data": current_date.isoformat(),
                    "dia_semana": day_key,
                    "tipo_dia": "FOLGA",
                    "entrada": None,
                    "saida": None,
                    "saida_no_dia_seguinte": False,
                }
            )

    return escala, total_minutes


def normalize_semanal_config(
    *,
    subtipo: str,
    intervalo_reduzido_convencao: bool,
    norma_coletiva_ref: str,
    dias_payload,
) -> dict:
    if subtipo not in SEMANAL_SUBTIPOS:
        raise ValidationError("Subtipo semanal inválido.")

    if not isinstance(dias_payload, list):
        raise ValidationError("Configuração semanal inválida: 'dias' deve ser uma lista.")

    normalized_days = []
    seen_days = set()
    work_days = 0

    for day in dias_payload:
        if not isinstance(day, dict):
            raise ValidationError("Configuração semanal inválida: cada dia deve ser um objeto.")

        day_name = str(day.get("dia_semana", "")).strip().upper()
        if day_name not in WEEK_DAYS:
            raise ValidationError(f"Dia da semana inválido: {day_name or 'vazio'}.")
        if day_name in seen_days:
            raise ValidationError(f"Dia da semana duplicado na configuração semanal: {day_name}.")
        seen_days.add(day_name)

        dsr = bool(day.get("dsr", False))
        entrada_1 = _to_hhmm(day.get("entrada_1"), field_label=f"{day_name} entrada 1")
        saida_1 = _to_hhmm(day.get("saida_1"), field_label=f"{day_name} saída 1")
        entrada_2 = _to_hhmm(day.get("entrada_2"), field_label=f"{day_name} entrada 2")
        saida_2 = _to_hhmm(day.get("saida_2"), field_label=f"{day_name} saída 2")

        if dsr:
            if any([entrada_1, saida_1, entrada_2, saida_2]):
                raise ValidationError(
                    f"{day_name}: não é permitido informar horários em dia marcado como DSR."
                )
            normalized_days.append({"dia_semana": day_name, "dsr": True})
            continue

        if not entrada_1 or not saida_1:
            raise ValidationError(f"{day_name}: entrada_1 e saída_1 são obrigatórios.")
        if _to_minutes(entrada_1) >= _to_minutes(saida_1):
            raise ValidationError(f"{day_name}: saída_1 deve ser maior que entrada_1.")

        has_second_period = bool(entrada_2 or saida_2)
        if has_second_period and (not entrada_2 or not saida_2):
            raise ValidationError(
                f"{day_name}: entrada_2 e saída_2 devem ser informados em conjunto."
            )
        if has_second_period:
            if _to_minutes(entrada_2) >= _to_minutes(saida_2):
                raise ValidationError(f"{day_name}: saída_2 deve ser maior que entrada_2.")
            if _to_minutes(saida_1) > _to_minutes(entrada_2):
                raise ValidationError(f"{day_name}: períodos não podem se sobrepor.")

        work_days += 1
        normalized_days.append(
            {
                "dia_semana": day_name,
                "dsr": False,
                "entrada_1": entrada_1,
                "saida_1": saida_1,
                "entrada_2": entrada_2,
                "saida_2": saida_2,
            }
        )

    if work_days == 0:
        raise ValidationError("Informe pelo menos um dia trabalhado com horários válidos.")

    norma = (norma_coletiva_ref or "").strip()
    if intervalo_reduzido_convencao and not norma:
        raise ValidationError(
            "Informe a referência da norma coletiva para intervalo reduzido por convenção."
        )

    return {
        "subtipo": subtipo,
        "intervalo_reduzido_convencao": bool(intervalo_reduzido_convencao),
        "norma_coletiva_ref": norma,
        "dias": normalized_days,
    }


def normalize_12x36_config(*, data_inicio_escala, horario_entrada) -> dict:
    if isinstance(data_inicio_escala, str):
        try:
            data_inicio = datetime.strptime(data_inicio_escala.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValidationError("Data de início da escala inválida.") from exc
    elif isinstance(data_inicio_escala, date):
        data_inicio = data_inicio_escala
    else:
        raise ValidationError("Informe a data de início da escala 12x36.")

    horario = _to_hhmm(horario_entrada, field_label="Horário de entrada da escala")
    if not horario:
        raise ValidationError("Informe o horário de entrada da escala 12x36.")
    horario_saida, _ = _add_hours_to_hhmm(horario, 12)
    escala_referencia_semanal, carga_horaria_semanal_minutos = _build_12x36_weekly_scale(
        data_inicio_escala=data_inicio,
        horario_entrada=horario,
        horario_saida=horario_saida,
    )

    return {
        "data_inicio_escala": data_inicio.isoformat(),
        "horario_entrada": horario,
        "horario_saida": horario_saida,
        "duracao_turno_horas": 12,
        "duracao_descanso_horas": 36,
        "ciclo_dias": [
            {"ordem": 1, "tipo_dia": "TRABALHO", "duracao_horas": 12},
            {"ordem": 2, "tipo_dia": "FOLGA", "duracao_horas": 36},
        ],
        "escala_referencia_semanal": escala_referencia_semanal,
        "carga_horaria_semanal_minutos": carga_horaria_semanal_minutos,
        "carga_horaria_semanal_hhmm": _minutes_to_hhmm(carga_horaria_semanal_minutos),
    }


def normalize_fracionada_config(
    *,
    intervalo_reduzido_convencao: bool,
    norma_coletiva_ref: str,
    dias_payload,
) -> dict:
    if not isinstance(dias_payload, list):
        raise ValidationError("Configuração fracionada inválida: 'dias' deve ser uma lista.")

    normalized_days = []
    seen_days = set()
    total_periods = 0

    for day in dias_payload:
        if not isinstance(day, dict):
            raise ValidationError("Configuração fracionada inválida: cada dia deve ser um objeto.")

        day_name = str(day.get("dia_semana", "")).strip().upper()
        if day_name not in WEEK_DAYS:
            raise ValidationError(f"Dia da semana inválido: {day_name or 'vazio'}.")
        if day_name in seen_days:
            raise ValidationError(f"Dia da semana duplicado na configuração fracionada: {day_name}.")
        seen_days.add(day_name)

        dsr = bool(day.get("dsr", False))
        periods_payload = day.get("periodos", [])
        if not isinstance(periods_payload, list):
            raise ValidationError(f"{day_name}: 'periodos' deve ser uma lista.")
        if dsr and periods_payload:
            raise ValidationError(f"{day_name}: não é permitido informar períodos quando o dia está em DSR.")

        normalized_periods = []
        last_end = None

        for index, period in enumerate(periods_payload, start=1):
            if not isinstance(period, dict):
                raise ValidationError(f"{day_name}: período {index} inválido.")
            start = _to_hhmm(period.get("inicio"), field_label=f"{day_name} período {index} início")
            end = _to_hhmm(period.get("fim"), field_label=f"{day_name} período {index} fim")
            if not start or not end:
                raise ValidationError(f"{day_name}: período {index} deve conter início e fim.")
            if _to_minutes(start) >= _to_minutes(end):
                raise ValidationError(f"{day_name}: período {index} possui intervalo inválido.")
            if last_end is not None and _to_minutes(start) <= _to_minutes(last_end):
                raise ValidationError(f"{day_name}: períodos devem estar em ordem e sem sobreposição.")
            normalized_periods.append({"inicio": start, "fim": end})
            last_end = end
            total_periods += 1

        normalized_days.append({"dia_semana": day_name, "dsr": dsr, "periodos": normalized_periods})

    if total_periods == 0:
        raise ValidationError("Informe ao menos um período válido na configuração fracionada.")

    norma = (norma_coletiva_ref or "").strip()
    if intervalo_reduzido_convencao and not norma:
        raise ValidationError(
            "Informe a referência da norma coletiva para intervalo reduzido por convenção."
        )

    return {
        "intervalo_reduzido_convencao": bool(intervalo_reduzido_convencao),
        "norma_coletiva_ref": norma,
        "dias": normalized_days,
    }


def normalize_externa_config(raw_config) -> dict:
    if raw_config not in (None, "", {}, []):
        raise ValidationError("Não é permitido definir horários para jornada externa.")
    return {}


def normalize_config_for_tipo(tipo: str, raw_config) -> dict:
    if tipo == "SEMANAL":
        if not isinstance(raw_config, dict):
            raise ValidationError("Configuração semanal inválida.")
        return normalize_semanal_config(
            subtipo=raw_config.get("subtipo", "PERSONALIZAR"),
            intervalo_reduzido_convencao=raw_config.get("intervalo_reduzido_convencao", False),
            norma_coletiva_ref=raw_config.get("norma_coletiva_ref", ""),
            dias_payload=raw_config.get("dias", []),
        )
    if tipo == "12X36":
        if not isinstance(raw_config, dict):
            raise ValidationError("Configuração 12x36 inválida.")
        return normalize_12x36_config(
            data_inicio_escala=raw_config.get("data_inicio_escala"),
            horario_entrada=raw_config.get("horario_entrada"),
        )
    if tipo == "FRACIONADA":
        if not isinstance(raw_config, dict):
            raise ValidationError("Configuração fracionada inválida.")
        return normalize_fracionada_config(
            intervalo_reduzido_convencao=raw_config.get("intervalo_reduzido_convencao", False),
            norma_coletiva_ref=raw_config.get("norma_coletiva_ref", ""),
            dias_payload=raw_config.get("dias", []),
        )
    if tipo == "EXTERNA":
        return normalize_externa_config(raw_config)
    raise ValidationError("Tipo de jornada inválido.")
