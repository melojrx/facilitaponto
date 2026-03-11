"""Integração de consulta de CNPJ com normalização e fallback manual."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .validators import only_digits

AUTO_FILL_FIELDS = {
    "razao_social": "razão social",
    "nome_fantasia": "nome fantasia",
    "email_contato": "e-mail",
    "telefone_contato": "telefone",
    "cep": "CEP",
    "logradouro": "logradouro",
    "numero": "número",
    "complemento": "complemento",
    "bairro": "bairro",
    "cidade": "cidade",
    "estado": "UF",
}


class CnpjLookupError(Exception):
    """Erro genérico na consulta de CNPJ."""


class CnpjNotFoundError(CnpjLookupError):
    """CNPJ inexistente no provider."""


class CnpjLookupTimeoutError(CnpjLookupError):
    """Timeout na consulta do provider."""


def _clean_text(value):
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _nested_get(payload, *path):
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _pick_first_text(*values):
    for value in values:
        if isinstance(value, dict):
            continue
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return ""


def _normalize_phone(value):
    if isinstance(value, list):
        for item in value:
            normalized = _normalize_phone(item)
            if normalized:
                return normalized
        return ""

    if isinstance(value, dict):
        return _pick_first_text(
            value.get("number"),
            value.get("phone"),
            value.get("full"),
            value.get("formatted"),
            f"{_clean_text(value.get('area'))}{_clean_text(value.get('number'))}",
        )

    return only_digits(_clean_text(value))


def _normalize_email(value):
    if isinstance(value, list):
        for item in value:
            normalized = _normalize_email(item)
            if normalized:
                return normalized
        return ""

    if isinstance(value, dict):
        return _pick_first_text(
            value.get("address"),
            value.get("email"),
            value.get("value"),
        ).lower()

    return _clean_text(value).lower()


def _normalize_city(value):
    if isinstance(value, dict):
        return _pick_first_text(value.get("name"), value.get("city"))
    return _clean_text(value)


def _normalize_state(value):
    if isinstance(value, dict):
        return _pick_first_text(value.get("code"), value.get("state")).upper()
    return _clean_text(value).upper()


def _normalize_payload(cnpj: str, payload: dict):
    company = payload.get("company") if isinstance(payload.get("company"), dict) else {}
    address = payload.get("address") if isinstance(payload.get("address"), dict) else {}

    normalized = {
        "documento": cnpj,
        "razao_social": _pick_first_text(
            company.get("name"),
            payload.get("companyName"),
            payload.get("name"),
        ),
        "nome_fantasia": _pick_first_text(
            company.get("alias"),
            payload.get("alias"),
            payload.get("trade"),
            payload.get("tradeName"),
        ),
        "email_contato": _normalize_email(
            payload.get("emails") or payload.get("email") or company.get("email")
        ),
        "telefone_contato": _normalize_phone(
            payload.get("phones") or payload.get("phone") or company.get("phone")
        ),
        "cep": only_digits(
            _pick_first_text(
                address.get("zip"),
                address.get("postalCode"),
                address.get("cep"),
            )
        )[:8],
        "logradouro": _pick_first_text(
            address.get("street"),
            address.get("logradouro"),
        ),
        "numero": _pick_first_text(
            address.get("number"),
            address.get("numero"),
        ),
        "complemento": _pick_first_text(
            address.get("details"),
            address.get("complement"),
            address.get("complemento"),
        ),
        "bairro": _pick_first_text(
            address.get("district"),
            address.get("neighborhood"),
            address.get("bairro"),
        ),
        "cidade": _normalize_city(address.get("city")),
        "estado": _normalize_state(address.get("state")),
    }

    missing_fields = [key for key in AUTO_FILL_FIELDS if not normalized.get(key)]
    return {
        "data": normalized,
        "meta": {
            "provider": "cnpja_open",
            "partial": bool(missing_fields),
            "missing_fields": missing_fields,
            "missing_labels": [AUTO_FILL_FIELDS[key] for key in missing_fields],
        },
    }


def lookup_cnpj_via_cnpja_open(cnpj: str, timeout: float | None = None):
    """Consulta CNPJ no provider Open da CNPJá e retorna dados normalizados."""
    normalized_cnpj = only_digits(cnpj)
    base_url = getattr(settings, "CNPJA_OPEN_BASE_URL", "https://open.cnpja.com").rstrip("/")
    timeout = timeout or getattr(settings, "CNPJA_OPEN_TIMEOUT", 4.0)
    endpoint = f"{base_url}/office/{normalized_cnpj}"
    request = Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "User-Agent": "FacilitaPonto/1.0",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise CnpjNotFoundError("CNPJ não encontrado.") from exc
        raise CnpjLookupError("Falha ao consultar CNPJá Open.") from exc
    except TimeoutError as exc:
        raise CnpjLookupTimeoutError("Consulta de CNPJ expirou.") from exc
    except URLError as exc:
        if isinstance(exc.reason, socket.timeout):
            raise CnpjLookupTimeoutError("Consulta de CNPJ expirou.") from exc
        raise CnpjLookupError("Falha ao consultar CNPJá Open.") from exc
    except OSError as exc:
        raise CnpjLookupError("Falha ao consultar CNPJá Open.") from exc
    except json.JSONDecodeError as exc:
        raise CnpjLookupError("Resposta inválida da CNPJá Open.") from exc

    return _normalize_payload(normalized_cnpj, payload)
