import json

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from .models import ConsentimentoBiometrico, FacialEmbedding


def has_active_consent(employee):
    """
    Retorna True quando o consentimento mais recente do funcionário está aceito.

    Regra explícita e simples para manter rastreabilidade:
    - sem consentimento: bloqueia
    - último consentimento recusado: bloqueia
    - último consentimento aceito: permite
    """
    latest_consent = ConsentimentoBiometrico.objects.filter(employee=employee).first()
    return bool(latest_consent and latest_consent.aceito)


def assert_active_consent(employee):
    """Dispara exceção quando não há consentimento biométrico ativo."""
    if not has_active_consent(employee):
        raise PermissionDenied("Consentimento biométrico obrigatório para esta operação.")


class DeepFaceAdapter:
    """
    Adapter fino para desacoplar a integração com DeepFace.

    Em testes, esse adapter pode ser mockado sem depender de processamento biométrico real.
    """

    @staticmethod
    def represent(image_bytes):
        import cv2
        import numpy as np
        from deepface import DeepFace

        image_np = np.frombuffer(image_bytes, dtype=np.uint8)
        image_bgr = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise ValidationError("Imagem inválida para processamento biométrico.")

        return DeepFace.represent(
            img_path=image_bgr,
            model_name="ArcFace",
            detector_backend="retinaface",
        )

    @staticmethod
    def verify(captured_embedding, stored_embedding):
        from deepface import DeepFace

        return DeepFace.verify(
            img1_path=captured_embedding,
            img2_path=stored_embedding,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=False,
            anti_spoofing=True,
        )


class BiometriaService:
    def __init__(self, adapter=None):
        self.adapter = adapter or DeepFaceAdapter
        key = settings.BIOMETRIA_KEY
        if isinstance(key, str):
            key = key.encode()
        self._fernet = Fernet(key)

    def cadastrar_embedding(self, employee, imagem_bytes):
        assert_active_consent(employee)

        embedding = self._extract_single_embedding(imagem_bytes)

        encrypted_embedding = self._fernet.encrypt(json.dumps(embedding).encode("utf-8"))

        FacialEmbedding.objects.filter(employee=employee, ativo=True).update(ativo=False)
        return FacialEmbedding.objects.create(
            employee=employee,
            embedding_data=encrypted_embedding,
            ativo=True,
        )

    def verificar(self, employee, imagem_bytes):
        active_embedding = FacialEmbedding.objects.filter(employee=employee, ativo=True).first()
        if active_embedding is None:
            raise ValidationError("Funcionário sem embedding biométrico ativo.")

        captured_embedding = self._extract_single_embedding(imagem_bytes)
        stored_embedding = self._decrypt_embedding(active_embedding.embedding_data)

        verification = self.adapter.verify(captured_embedding, stored_embedding)
        authenticated = bool(verification.get("verified", False))
        distance = float(verification.get("distance", 1.0))
        threshold = verification.get("threshold", 0.68)
        threshold = float(0.68 if threshold is None else threshold)

        return {
            "autenticado": authenticated,
            "distancia": distance,
            "threshold": threshold,
        }

    def _extract_single_embedding(self, imagem_bytes):
        if not imagem_bytes:
            raise ValidationError("Imagem obrigatória para processamento biométrico.")

        representations = self.adapter.represent(imagem_bytes)
        if not representations:
            raise ValidationError("Nenhum rosto detectado para processamento biométrico.")
        if len(representations) != 1:
            raise ValidationError("A imagem deve conter exatamente um rosto.")

        embedding = representations[0].get("embedding")
        if not embedding:
            raise ValidationError("Falha ao gerar embedding facial.")

        return embedding

    def _decrypt_embedding(self, encrypted_embedding):
        try:
            if isinstance(encrypted_embedding, memoryview):
                encrypted_embedding = encrypted_embedding.tobytes()

            raw = self._fernet.decrypt(encrypted_embedding)
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValidationError("Falha ao descriptografar embedding facial.") from exc
