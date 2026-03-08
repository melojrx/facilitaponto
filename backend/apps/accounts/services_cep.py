"""Integração de consulta de CEP (ViaCEP) com normalização e fallback manual."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class CepLookupError(Exception):
    """Erro genérico na consulta de CEP."""


class CepNotFoundError(CepLookupError):
    """CEP inexistente no provider."""


def lookup_cep_via_viacep(cep: str, timeout: float = 3.0):
    """Consulta CEP no ViaCEP e retorna campos normalizados de endereço."""
    endpoint = f"https://viacep.com.br/ws/{cep}/json/"
    try:
        with urlopen(endpoint, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CepLookupError("Falha ao consultar ViaCEP.") from exc
    except json.JSONDecodeError as exc:
        raise CepLookupError("Resposta inválida do ViaCEP.") from exc

    if payload.get("erro"):
        raise CepNotFoundError("CEP não encontrado.")

    return {
        "cep": "".join(ch for ch in str(payload.get("cep", "")) if ch.isdigit())[:8],
        "logradouro": (payload.get("logradouro") or "").strip(),
        "bairro": (payload.get("bairro") or "").strip(),
        "cidade": (payload.get("localidade") or "").strip(),
        "estado": (payload.get("uf") or "").strip().upper(),
    }
