import hashlib

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.biometrics.services import BiometriaService
from apps.employees.models import Employee
from apps.employees.services import get_next_nsr
from apps.legal_files.services import ComprovanteService

from .models import AttendanceRecord
from .storage import AttendancePhotoStorageService


class AttendanceService:
    def __init__(self, biometria_service=None, comprovante_service=None, photo_storage_service=None):
        self.biometria_service = biometria_service or BiometriaService()
        self.comprovante_service = comprovante_service or ComprovanteService()
        self.photo_storage_service = photo_storage_service or AttendancePhotoStorageService()

    def registrar(
        self,
        employee,
        tipo,
        imagem_bytes,
        timestamp=None,
        origem=AttendanceRecord.Origem.ONLINE,
        client_event_id=None,
        latitude=None,
        longitude=None,
    ):
        if not employee.ativo:
            raise ValidationError("Funcionário inativo não pode registrar ponto.")

        self._validate_tipo(tipo)
        timestamp = timestamp or timezone.now()

        existing_record = self._find_existing_by_client_event_id(
            employee=employee,
            client_event_id=client_event_id,
        )
        if existing_record is not None:
            self._validate_existing_idempotency(existing_record, employee, tipo, timestamp)
            return existing_record, False

        self._validate_sequence(employee, tipo)
        biometria = self.biometria_service.verificar(employee, imagem_bytes)
        if not biometria.get("autenticado", False):
            raise ValidationError("Biometria não autenticada para registro de ponto.")

        foto_hash = hashlib.sha256(imagem_bytes).hexdigest()
        foto_path = self.photo_storage_service.upload_attendance_photo(
            tenant_id=employee.tenant_id,
            timestamp=timestamp,
            foto_hash=foto_hash,
            imagem_bytes=imagem_bytes,
        )
        with transaction.atomic():
            nsr = get_next_nsr(employee.tenant_id)

            record = AttendanceRecord.all_objects.create(
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
                client_event_id=client_event_id,
                sincronizado_em=timezone.now() if origem == AttendanceRecord.Origem.OFFLINE else None,
            )
            self.comprovante_service.gerar(record)
            return record, True

    def sincronizar_lote(self, tenant, registros):
        results = []
        employee_ids = sorted({item["employee_id"] for item in registros})
        employees = {
            employee.id: employee
            for employee in Employee.objects.filter(
                tenant=tenant,
                ativo=True,
                id__in=employee_ids,
            )
        }

        missing_ids = [employee_id for employee_id in employee_ids if employee_id not in employees]
        if missing_ids:
            missing = ", ".join(str(item) for item in missing_ids)
            raise ValidationError(f"Funcionário(s) não encontrado(s) para o tenant: {missing}.")

        for item in registros:
            employee = employees[item["employee_id"]]
            record, created = self.registrar(
                employee=employee,
                tipo=item["tipo"],
                imagem_bytes=item["imagem_base64"],
                timestamp=item["timestamp"],
                origem=AttendanceRecord.Origem.OFFLINE,
                client_event_id=item["client_event_id"],
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
            )
            results.append(
                {
                    "client_event_id": item["client_event_id"],
                    "created": created,
                    "record": record,
                }
            )

        return results

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
    def _find_existing_by_client_event_id(employee, client_event_id):
        if not client_event_id:
            return None

        return AttendanceRecord.all_objects.filter(
            tenant_id=employee.tenant_id,
            client_event_id=client_event_id,
        ).first()

    @staticmethod
    def _validate_existing_idempotency(existing_record, employee, tipo, timestamp):
        if (
            existing_record.employee_id != employee.id
            or existing_record.tipo != tipo
            or existing_record.timestamp != timestamp
        ):
            raise ValidationError(
                "client_event_id já utilizado com dados diferentes no tenant."
            )
