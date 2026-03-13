import json
from dataclasses import dataclass
from urllib import error, request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError


@dataclass(frozen=True)
class WhatsAppSendResult:
    provider: str
    message_id: str
    payload: dict


class WhatsAppProvider:
    provider_name = "base"

    def send_biometric_invite(self, *, phone_number, message_text, metadata=None):
        raise NotImplementedError


class WahaWhatsAppProvider(WhatsAppProvider):
    provider_name = "waha"

    def __init__(self, *, base_url, session_name, api_token="", timeout=5.0):
        self.base_url = (base_url or "").rstrip("/")
        self.session_name = (session_name or "").strip()
        self.api_token = (api_token or "").strip()
        self.timeout = timeout

        if not self.base_url:
            raise ImproperlyConfigured("WHATSAPP_WAHA_BASE_URL obrigatoria para usar WAHA.")
        if not self.session_name:
            raise ImproperlyConfigured("WHATSAPP_WAHA_SESSION obrigatoria para usar WAHA.")

    def send_biometric_invite(self, *, phone_number, message_text, metadata=None):
        url = f"{self.base_url}/api/sendText"
        payload = {
            "session": self.session_name,
            "chatId": self._build_chat_id(phone_number),
            "text": message_text,
        }

        if metadata:
            payload["metadata"] = metadata

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        raw_body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(url, data=raw_body, headers=headers, method="POST")

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8") or "{}"
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ValidationError(
                f"Falha ao enviar link por WhatsApp via WAHA. {detail or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise ValidationError(
                "Falha ao conectar ao provider de WhatsApp. Tente novamente."
            ) from exc

        parsed_payload = json.loads(response_body)
        message_id = str(
            parsed_payload.get("id")
            or parsed_payload.get("messageId")
            or parsed_payload.get("message", {}).get("id")
            or ""
        )

        return WhatsAppSendResult(
            provider=self.provider_name,
            message_id=message_id,
            payload=parsed_payload,
        )

    @staticmethod
    def _build_chat_id(phone_number):
        digits = "".join(character for character in phone_number if character.isdigit())
        if not digits:
            raise ValidationError("Telefone invalido para envio por WhatsApp.")
        if digits.startswith("55"):
            return f"{digits}@c.us"
        return f"55{digits}@c.us"


def build_whatsapp_provider():
    provider_name = settings.WHATSAPP_PROVIDER.lower()

    if provider_name == "waha":
        return WahaWhatsAppProvider(
            base_url=settings.WHATSAPP_WAHA_BASE_URL,
            session_name=settings.WHATSAPP_WAHA_SESSION,
            api_token=settings.WHATSAPP_WAHA_API_TOKEN,
            timeout=settings.WHATSAPP_TIMEOUT,
        )

    raise ImproperlyConfigured(f"Provider de WhatsApp nao suportado: {settings.WHATSAPP_PROVIDER}")
