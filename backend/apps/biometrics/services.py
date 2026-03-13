import json
import secrets
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.employees.validators import normalize_optional_phone

from .models import BiometricInvite, ConsentimentoBiometrico, FacialEmbedding
from .providers import build_whatsapp_provider


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


class AssistedBiometricCaptureService:
    """Orquestra captura biométrica assistida no painel web."""

    DEFAULT_TERM_VERSION = "painel-v1"

    def __init__(self, *, biometria_service=None):
        self.biometria_service = biometria_service or BiometriaService()

    def capture_for_panel(
        self,
        *,
        employee,
        imagem_bytes,
        consentimento_aceito,
        versao_termo=None,
        ip_origem=None,
    ):
        if not consentimento_aceito:
            raise ValidationError(
                "Marque a autorização para confirmar o cadastro facial."
            )

        if not imagem_bytes:
            raise ValidationError("Envie uma foto facial válida para continuar.")

        term_version = (versao_termo or self.DEFAULT_TERM_VERSION).strip()
        if not term_version:
            term_version = self.DEFAULT_TERM_VERSION

        consent = self._register_consent(
            employee=employee,
            versao_termo=term_version,
            ip_origem=ip_origem,
        )

        embedding = self.biometria_service.cadastrar_embedding(employee, imagem_bytes)
        employee.refresh_from_db()

        return {
            "consent": consent,
            "embedding": embedding,
            "snapshot": employee.biometric_snapshot(),
        }

    @staticmethod
    @transaction.atomic
    def _register_consent(*, employee, versao_termo, ip_origem):
        return ConsentimentoBiometrico.objects.create(
            employee=employee,
            aceito=True,
            versao_termo=versao_termo,
            ip_origem=ip_origem,
        )


class BiometricInviteService:
    """Servico de envio do convite biometrico remoto por WhatsApp."""

    SELF_ENROLL_TERM_VERSION = "whatsapp-v1"

    def __init__(self, *, provider=None, assisted_capture_service=None):
        self.provider = provider
        self.assisted_capture_service = assisted_capture_service or AssistedBiometricCaptureService()

    def send_whatsapp_invite(self, *, employee, requested_by):
        if not requested_by.tenant_id or requested_by.tenant_id != employee.tenant_id:
            raise PermissionDenied("Nao e permitido enviar convite biometrico para outro tenant.")

        phone_number = normalize_optional_phone(employee.telefone)
        if not phone_number:
            raise ValidationError("Telefone invalido para envio por WhatsApp.")

        provider = self.provider or build_whatsapp_provider()

        with transaction.atomic():
            self._revoke_previous_active_invites(employee=employee)

            raw_token = secrets.token_urlsafe(32)
            invite = BiometricInvite.all_objects.create(
                tenant=employee.tenant,
                employee=employee,
                created_by=requested_by,
                channel=BiometricInvite.Channel.WHATSAPP,
                provider=provider.provider_name,
                sent_to=phone_number,
                token_hash=BiometricInvite.build_token_hash(raw_token),
                expires_at=timezone.now() + timedelta(hours=settings.BIOMETRIC_INVITE_EXPIRATION_HOURS),
                status=BiometricInvite.Status.PENDING,
            )

        invite_url = self._build_invite_url(raw_token)
        message_text = self._build_message(employee=employee, invite_url=invite_url)

        try:
            delivery = provider.send_biometric_invite(
                phone_number=phone_number,
                message_text=message_text,
                metadata={
                    "employee_id": employee.id,
                    "tenant_id": str(employee.tenant_id),
                    "invite_id": invite.id,
                    "channel": BiometricInvite.Channel.WHATSAPP,
                },
            )
        except ValidationError as exc:
            invite.status = BiometricInvite.Status.FAILED
            invite.last_error = "; ".join(exc.messages)
            invite.save(update_fields=["status", "last_error", "updated_at"])
            raise

        invite.status = BiometricInvite.Status.SENT
        invite.sent_at = timezone.now()
        invite.provider = delivery.provider
        invite.provider_message_id = delivery.message_id
        invite.provider_payload = delivery.payload
        invite.last_error = ""
        invite.save(
            update_fields=[
                "status",
                "sent_at",
                "provider",
                "provider_message_id",
                "provider_payload",
                "last_error",
                "updated_at",
            ]
        )

        return {
            "invite": invite,
            "invite_url": invite_url,
        }

    @transaction.atomic
    def complete_self_enroll(
        self,
        *,
        raw_token,
        imagem_bytes,
        consentimento_aceito,
        versao_termo=None,
        ip_origem=None,
    ):
        invite = self._get_invite_by_token(raw_token=raw_token, for_update=True)
        self._assert_invite_available(invite)

        result = self.assisted_capture_service.capture_for_panel(
            employee=invite.employee,
            imagem_bytes=imagem_bytes,
            consentimento_aceito=consentimento_aceito,
            versao_termo=versao_termo or self.SELF_ENROLL_TERM_VERSION,
            ip_origem=ip_origem,
        )

        invite.status = BiometricInvite.Status.USED
        invite.used_at = timezone.now()
        invite.last_error = ""
        invite.save(update_fields=["status", "used_at", "last_error", "updated_at"])

        return {
            "invite": invite,
            **result,
        }

    def get_invite_for_token(self, *, raw_token):
        invite = self._get_invite_by_token(raw_token=raw_token, for_update=False)
        self._assert_invite_available(invite)
        return invite

    @staticmethod
    def _revoke_previous_active_invites(*, employee):
        now = timezone.now()
        active_statuses = [BiometricInvite.Status.PENDING, BiometricInvite.Status.SENT]
        queryset = BiometricInvite.all_objects.filter(
            employee=employee,
            status__in=active_statuses,
            used_at__isnull=True,
        )

        expiring_ids = list(queryset.filter(expires_at__lte=now).values_list("id", flat=True))
        if expiring_ids:
            BiometricInvite.all_objects.filter(id__in=expiring_ids).update(
                status=BiometricInvite.Status.EXPIRED,
                updated_at=now,
            )

        queryset.filter(expires_at__gt=now).update(
            status=BiometricInvite.Status.REVOKED,
            updated_at=now,
        )

    @staticmethod
    def _build_invite_url(raw_token):
        base_url = settings.BIOMETRIC_SELF_ENROLL_BASE_URL.rstrip("/")
        if not base_url:
            raise ValidationError("BIOMETRIC_SELF_ENROLL_BASE_URL nao configurada.")
        return f"{base_url}?token={raw_token}"

    @staticmethod
    def _build_message(*, employee, invite_url):
        return (
            f"Ola, {employee.nome}. "
            "Use este link para concluir seu cadastro facial no sistema de ponto: "
            f"{invite_url}"
        )

    @staticmethod
    def _get_invite_by_token(*, raw_token, for_update):
        token = (raw_token or "").strip()
        if not token:
            raise ValidationError("Link de cadastro facial invalido ou expirado.")

        token_hash = BiometricInvite.build_token_hash(token)
        queryset = (
            BiometricInvite.all_objects.select_related("employee", "employee__tenant")
            .prefetch_related("employee__consentimentos_biometricos", "employee__facial_embeddings")
        )
        if for_update:
            queryset = queryset.select_for_update()

        try:
            return queryset.get(token_hash=token_hash)
        except BiometricInvite.DoesNotExist as exc:
            raise ValidationError("Link de cadastro facial invalido ou expirado.") from exc

    @staticmethod
    def _assert_invite_available(invite):
        now = timezone.now()

        if invite.expires_at <= now:
            if invite.status != BiometricInvite.Status.EXPIRED:
                invite.status = BiometricInvite.Status.EXPIRED
                invite.save(update_fields=["status", "updated_at"])
            raise ValidationError(
                "Este link de cadastro facial expirou. Solicite um novo envio ao gestor da empresa."
            )

        if invite.used_at or invite.status == BiometricInvite.Status.USED:
            raise ValidationError(
                "Este link de cadastro facial ja foi utilizado. Se precisar refazer o cadastro, solicite um novo envio ao gestor."
            )

        if invite.status == BiometricInvite.Status.REVOKED:
            raise ValidationError(
                "Este link de cadastro facial foi substituido por um novo envio. Solicite o link atualizado ao gestor."
            )

        if invite.status == BiometricInvite.Status.FAILED:
            raise ValidationError(
                "Este link de cadastro facial nao esta mais disponivel. Solicite um novo envio ao gestor."
            )
