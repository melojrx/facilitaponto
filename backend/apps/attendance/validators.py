"""Validadores e normalizadores do dominio de relogios de ponto."""

from django.core.exceptions import ValidationError


def normalize_time_clock_text(value):
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def validate_time_clock_name(value):
    normalized = normalize_time_clock_text(value)
    if not normalized:
        raise ValidationError("Informe o nome do relógio.")
    if len(normalized) < 3:
        raise ValidationError("O nome do relógio deve ter pelo menos 3 caracteres.")
    if len(normalized) > 80:
        raise ValidationError("O nome do relógio deve ter no máximo 80 caracteres.")
    return normalized


def validate_activation_code(value):
    normalized = normalize_time_clock_text(value).upper()
    if not normalized:
        raise ValidationError("Código de ativação é obrigatório.")
    if len(normalized) != 6 or not normalized.isalnum():
        raise ValidationError("Código de ativação inválido.")
    return normalized


def validate_latitude(value):
    if value is None:
        return
    if value < -90 or value > 90:
        raise ValidationError("Latitude deve estar entre -90 e 90.")


def validate_longitude(value):
    if value is None:
        return
    if value < -180 or value > 180:
        raise ValidationError("Longitude deve estar entre -180 e 180.")


def validate_radius_meters(value):
    if value is None:
        raise ValidationError("Informe o raio da cerca virtual.")
    if int(value) <= 0:
        raise ValidationError("O raio da cerca virtual deve ser maior que zero.")
