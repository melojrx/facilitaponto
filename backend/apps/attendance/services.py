import hashlib

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.biometrics.services import BiometriaService
from apps.employees.services import get_next_nsr

from .models import AttendanceRecord


class AttendanceService:
    def __init__(self, biometria_service=None):
        self.biometria_service = biometria_service or BiometriaService()

    def registrar(
        self,
        employee,
        tipo,
        imagem_bytes,
        timestamp=None,
        origem=AttendanceRecord.Origem.ONLINE,
        latitude=None,
        longitude=None,
    ):
        if not employee.ativo:
            raise ValidationError("Funcionário inativo não pode registrar ponto.")

        self._validate_tipo(tipo)
        self._validate_sequence(employee, tipo)

        biometria = self.biometria_service.verificar(employee, imagem_bytes)
        if not biometria.get("autenticado", False):
            raise ValidationError("Biometria não autenticada para registro de ponto.")

        timestamp = timestamp or timezone.now()
        foto_hash = hashlib.sha256(imagem_bytes).hexdigest()
        foto_path = self._build_foto_path(employee.tenant_id, timestamp, foto_hash)
        nsr = get_next_nsr(employee.tenant_id)

        return AttendanceRecord.all_objects.create(
            tenant=employee.tenant,
            employee=employee,
            tipo=tipo,
            timestamp=timestamp,
            nsr=nsr,
            latitude=latitude,
            longitude=longitude,
            foto_path=foto_path,
            foto_hash=foto_hash,
            confianca_biometrica=self._distance_to_confidence(biometria.get("distancia")),
            origem=origem,
            sincronizado_em=timezone.now() if origem == AttendanceRecord.Origem.OFFLINE else None,
        )

    @staticmethod
    def _validate_tipo(tipo):
        valid_tipos = {item[0] for item in AttendanceRecord.Tipo.choices}
        if tipo not in valid_tipos:
            raise ValidationError("Tipo de marcação inválido.")

    def _validate_sequence(self, employee, current_tipo):
        last_record = (
            AttendanceRecord.all_objects.filter(
                tenant_id=employee.tenant_id,
                employee=employee,
            )
            .order_by("-timestamp", "-id")
            .first()
        )

        if last_record is None:
            if current_tipo != AttendanceRecord.Tipo.ENTRADA:
                raise ValidationError("Primeira marcação do ciclo deve ser Entrada (E).")
            return

        allowed_transitions = {
            AttendanceRecord.Tipo.ENTRADA: {
                AttendanceRecord.Tipo.INICIO_INTERVALO,
                AttendanceRecord.Tipo.SAIDA,
            },
            AttendanceRecord.Tipo.INICIO_INTERVALO: {AttendanceRecord.Tipo.FIM_INTERVALO},
            AttendanceRecord.Tipo.FIM_INTERVALO: {AttendanceRecord.Tipo.SAIDA},
            AttendanceRecord.Tipo.SAIDA: {AttendanceRecord.Tipo.ENTRADA},
        }

        allowed = allowed_transitions[last_record.tipo]
        if current_tipo not in allowed:
            allowed_list = ", ".join(sorted(allowed))
            raise ValidationError(
                f"Ordem de batidas inválida: após {last_record.tipo} só é permitido {allowed_list}."
            )

    @staticmethod
    def _distance_to_confidence(distance):
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return 0.0

        return max(0.0, min(1.0, 1.0 - value))

    @staticmethod
    def _build_foto_path(tenant_id, timestamp, foto_hash):
        day = timestamp.astimezone(timezone.get_current_timezone()).strftime("%Y/%m/%d")
        return f"attendance/{tenant_id}/{day}/{foto_hash}.jpg"
