"""Validadores e normalizadores do dominio de colaboradores."""

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.validators import is_valid_cpf, only_digits

PIS_WEIGHTS = (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def normalize_optional_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_optional_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_optional_phone(value: str) -> str:
    digits = only_digits(value)
    if not digits:
        return ""
    if len(digits) not in (10, 11):
        raise ValidationError("Telefone invalido para o colaborador.")
    return digits


def is_valid_pis(pis: str) -> bool:
    if len(pis) != 11:
        return False
    if pis == pis[0] * 11:
        return False

    total = sum(int(digit) * weight for digit, weight in zip(pis[:10], PIS_WEIGHTS, strict=False))
    remainder = 11 - (total % 11)
    check_digit = 0 if remainder in (10, 11) else remainder
    return check_digit == int(pis[10])


def validate_employee_name(value: str) -> str:
    normalized = normalize_optional_text(value)
    if len(normalized) < 3:
        raise ValidationError("Informe o nome completo do colaborador.")
    return normalized


def validate_employee_cpf(value: str) -> str:
    digits = only_digits(value)
    if not is_valid_cpf(digits):
        raise ValidationError("Informe um CPF valido com 11 digitos.")
    return digits


def validate_employee_pis(value: str) -> str:
    digits = only_digits(value)
    if not is_valid_pis(digits):
        raise ValidationError("Informe um PIS/PASEP valido com 11 digitos.")
    return digits


def validate_not_future(value, message="Data invalida."):
    if value and value > timezone.localdate():
        raise ValidationError(message)
    return value
