import base64
import binascii

from django import forms
from django.core.exceptions import ValidationError

from .services import AssistedBiometricCaptureService


class AssistedBiometricCaptureForm(forms.Form):
    imagem = forms.ImageField(
        required=False,
        error_messages={
            "invalid_image": "Envie uma foto facial válida para continuar.",
        },
    )
    imagem_capturada = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    consentimento = forms.BooleanField(
        required=True,
        error_messages={
            "required": "Marque a autorização para confirmar o cadastro facial.",
        },
    )
    versao_termo = forms.CharField(
        initial=AssistedBiometricCaptureService.DEFAULT_TERM_VERSION,
        widget=forms.HiddenInput(),
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        uploaded_image = cleaned_data.get("imagem")
        captured_image = (cleaned_data.get("imagem_capturada") or "").strip()

        if uploaded_image:
            cleaned_data["imagem_bytes"] = uploaded_image.read()
            return cleaned_data

        if not captured_image:
            raise ValidationError("Envie uma foto facial válida para continuar.")

        cleaned_data["imagem_bytes"] = self._decode_captured_image(captured_image)
        return cleaned_data

    @staticmethod
    def _decode_captured_image(captured_image):
        payload = captured_image
        if payload.startswith("data:"):
            try:
                _, payload = payload.split(",", 1)
            except ValueError as exc:
                raise ValidationError("Envie uma foto facial válida para continuar.") from exc

        try:
            return base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValidationError("Envie uma foto facial válida para continuar.") from exc
