import hashlib
import secrets
import string
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Device
from apps.biometrics.services import BiometriaService
from apps.employees.models import Employee
from apps.employees.services import get_next_nsr
from apps.legal_files.services import ComprovanteService

from .models import (
    AttendanceRecord,
    TimeClock,
    TimeClockEmployeeAssignment,
    TimeClockGeofence,
)
from .storage import AttendancePhotoStorageService
from .validators import validate_activation_code


class TimeClockService:
    """Servico transacional para o dominio de relogios de ponto."""

    ACTIVATION_CODE_ALPHABET = string.ascii_uppercase + string.digits
    ACTIVATION_CODE_LENGTH = 6

    def get_time_clock_for_device(self, *, tenant, device):
        if device is None:
            raise ValidationError("Dispositivo não autenticado para operação do relógio.")

        time_clock = (
            TimeClock.all_objects.filter(
                tenant=tenant,
                current_device=device,
            )
            .select_related("current_device")
            .prefetch_related("employees")
            .first()
        )
        if time_clock is None:
            raise ValidationError("Nenhum relógio ativo está vinculado a este dispositivo.")
        return time_clock

    def create_time_clock(
        self,
        *,
        tenant,
        user,
        nome,
        descricao="",
        tipo_relogio=TimeClock.TipoRelogio.APLICATIVO,
        status=TimeClock.Status.ATIVO,
        plataforma=TimeClock.Plataforma.DESCONHECIDA,
        current_device=None,
    ):
        device = self._resolve_device(tenant=tenant, current_device=current_device)

        with transaction.atomic():
            time_clock = TimeClock(
                tenant=tenant,
                created_by=user,
                nome=nome,
                descricao=descricao,
                tipo_relogio=tipo_relogio,
                status=status,
                plataforma=plataforma,
                current_device=device,
                activation_code=self._generate_unique_activation_code(),
            )
            time_clock.full_clean()
            time_clock.save()
            return time_clock

    def activate_time_clock(
        self,
        *,
        activation_code,
        device_id,
        nome_dispositivo="",
        plataforma=TimeClock.Plataforma.DESCONHECIDA,
    ):
        normalized_code = validate_activation_code(activation_code)
        normalized_device_id = (device_id or "").strip()
        if not normalized_device_id:
            raise ValidationError({"device_id": "device_id é obrigatório."})

        valid_platforms = {choice[0] for choice in TimeClock.Plataforma.choices}
        if plataforma not in valid_platforms:
            raise ValidationError({"plataforma": "Plataforma inválida para o relógio."})

        try:
            time_clock = TimeClock.all_objects.select_related("tenant").get(
                activation_code=normalized_code
            )
        except TimeClock.DoesNotExist as exc:
            raise ValidationError({"activation_code": "Código de ativação inválido ou expirado."}) from exc

        if time_clock.status != TimeClock.Status.ATIVO:
            raise ValidationError("Relógio indisponível para ativação no momento.")

        with transaction.atomic():
            device, _ = Device.objects.update_or_create(
                tenant=time_clock.tenant,
                device_id=normalized_device_id,
                defaults={
                    "nome": (nome_dispositivo or "").strip(),
                    "ativo": True,
                    "last_seen_at": timezone.now(),
                },
            )
            time_clock.current_device = device
            time_clock.plataforma = plataforma
            time_clock.last_synced_at = timezone.now()
            time_clock.full_clean()
            time_clock.save(
                update_fields=[
                    "current_device",
                    "plataforma",
                    "last_synced_at",
                    "updated_at",
                ]
            )
            return time_clock, device

    def update_time_clock(
        self,
        *,
        time_clock,
        nome,
        descricao="",
        tipo_relogio=None,
        status=None,
        plataforma=None,
        current_device=None,
    ):
        if tipo_relogio is not None:
            time_clock.tipo_relogio = tipo_relogio
        if status is not None:
            time_clock.status = status
        if plataforma is not None:
            time_clock.plataforma = plataforma

        time_clock.nome = nome
        time_clock.descricao = descricao
        time_clock.current_device = self._resolve_device(
            tenant=time_clock.tenant,
            current_device=current_device,
        )
        time_clock.full_clean()
        time_clock.save()
        return time_clock

    def update_time_clock_status(self, *, time_clock, status):
        time_clock.status = status
        time_clock.full_clean()
        time_clock.save(update_fields=["status", "updated_at"])
        return time_clock

    def regenerate_activation_code(self, *, time_clock):
        time_clock.activation_code = self._generate_unique_activation_code()
        time_clock.full_clean()
        time_clock.save(update_fields=["activation_code", "updated_at"])
        return time_clock

    def configure_geofence(
        self,
        *,
        time_clock,
        latitude,
        longitude,
        raio_metros,
        ativo=True,
    ):
        with transaction.atomic():
            geofence, _ = TimeClockGeofence.all_objects.update_or_create(
                time_clock=time_clock,
                defaults={
                    "tenant": time_clock.tenant,
                    "latitude": self._normalize_coordinate(latitude),
                    "longitude": self._normalize_coordinate(longitude),
                    "raio_metros": raio_metros,
                    "ativo": ativo,
                },
            )
            geofence.full_clean()
            geofence.save()
            return geofence

    def disable_geofence(self, *, time_clock):
        geofence = getattr(time_clock, "geofence", None)
        if geofence is None:
            return None

        geofence.ativo = False
        geofence.full_clean()
        geofence.save(update_fields=["ativo", "updated_at"])
        return geofence

    def validate_attendance_prerequisites(
        self,
        *,
        time_clock,
        employee,
        latitude=None,
        longitude=None,
    ):
        if time_clock.status == TimeClock.Status.INATIVO:
            raise ValidationError("Relógio inativo.")
        if time_clock.status == TimeClock.Status.EM_MANUTENCAO:
            raise ValidationError("Relógio em manutenção. Tente novamente após liberação.")
        if not employee.ativo:
            raise ValidationError("Funcionário inativo não pode registrar ponto.")
        if not TimeClockEmployeeAssignment.all_objects.filter(
            tenant=time_clock.tenant,
            time_clock=time_clock,
            employee=employee,
        ).exists():
            raise ValidationError("Colaborador não está atribuído a este relógio.")

        biometric_snapshot = employee.biometric_snapshot()
        if not biometric_snapshot["has_active_embedding"]:
            raise ValidationError("Autenticação facial não concluída para o colaborador.")

        geofence = getattr(time_clock, "geofence", None)
        if geofence and geofence.ativo:
            if latitude is None or longitude is None:
                raise ValidationError("Batida fora da cerca virtual não permitida para este relógio.")
            if not self._coordinates_within_geofence(
                latitude=latitude,
                longitude=longitude,
                geofence=geofence,
            ):
                raise ValidationError("Batida fora da cerca virtual não permitida para este relógio.")

    def available_employees_queryset(self, *, time_clock, search=""):
        queryset = (
            Employee.all_objects.filter(tenant=time_clock.tenant, ativo=True)
            .exclude(time_clock_assignments__time_clock=time_clock)
            .order_by("nome", "id")
        )
        return self._apply_employee_search(queryset, search=search)

    def assigned_employees_queryset(self, *, time_clock, search=""):
        queryset = (
            Employee.all_objects.filter(
                tenant=time_clock.tenant,
                time_clock_assignments__time_clock=time_clock,
            )
            .distinct()
            .order_by("nome", "id")
        )
        return self._apply_employee_search(queryset, search=search)

    def assign_employees(self, *, time_clock, employee_ids):
        normalized_ids = self._normalize_employee_ids(employee_ids)
        if not normalized_ids:
            return 0

        employees = list(
            Employee.all_objects.filter(
                tenant=time_clock.tenant,
                ativo=True,
                id__in=normalized_ids,
            )
        )
        resolved_ids = {employee.id for employee in employees}
        if resolved_ids != normalized_ids:
            raise ValidationError(
                {"employees": "Selecione apenas colaboradores ativos e válidos da sua empresa."}
            )

        existing_ids = set(
            TimeClockEmployeeAssignment.all_objects.filter(
                tenant=time_clock.tenant,
                time_clock=time_clock,
                employee_id__in=normalized_ids,
            ).values_list("employee_id", flat=True)
        )
        assignments = [
            TimeClockEmployeeAssignment(
                tenant=time_clock.tenant,
                time_clock=time_clock,
                employee=employee,
            )
            for employee in employees
            if employee.id not in existing_ids
        ]
        if not assignments:
            return 0

        for assignment in assignments:
            assignment.full_clean()

        TimeClockEmployeeAssignment.all_objects.bulk_create(assignments)
        return len(assignments)

    def assign_all_employees(self, *, time_clock, search=""):
        employee_ids = self.available_employees_queryset(
            time_clock=time_clock,
            search=search,
        ).values_list("id", flat=True)
        return self.assign_employees(time_clock=time_clock, employee_ids=employee_ids)

    def remove_employees(self, *, time_clock, employee_ids):
        normalized_ids = self._normalize_employee_ids(employee_ids)
        if not normalized_ids:
            return 0

        valid_ids = set(
            Employee.all_objects.filter(
                tenant=time_clock.tenant,
                id__in=normalized_ids,
            ).values_list("id", flat=True)
        )
        if valid_ids != normalized_ids:
            raise ValidationError(
                {"employees": "Selecione apenas colaboradores válidos da sua empresa."}
            )

        deleted_count, _ = TimeClockEmployeeAssignment.all_objects.filter(
            tenant=time_clock.tenant,
            time_clock=time_clock,
            employee_id__in=normalized_ids,
        ).delete()
        return deleted_count

    def remove_all_employees(self, *, time_clock, search=""):
        employee_ids = self.assigned_employees_queryset(
            time_clock=time_clock,
            search=search,
        ).values_list("id", flat=True)
        return self.remove_employees(time_clock=time_clock, employee_ids=employee_ids)

    def _resolve_device(self, *, tenant, current_device):
        if current_device in (None, ""):
            return None

        if isinstance(current_device, Device):
            device = current_device
        else:
            device = Device.objects.filter(tenant=tenant, pk=current_device).first()

        if device is None or device.tenant_id != tenant.id:
            raise ValidationError({"current_device": "Selecione um dispositivo válido da sua empresa."})

        return device

    def _generate_unique_activation_code(self):
        for _ in range(20):
            candidate = "".join(
                secrets.choice(self.ACTIVATION_CODE_ALPHABET)
                for _ in range(self.ACTIVATION_CODE_LENGTH)
            )
            if not TimeClock.all_objects.filter(activation_code=candidate).exists():
                return candidate

        raise ValidationError(
            "Não foi possível gerar um código de ativação único para o relógio."
        )

    @staticmethod
    def _normalize_coordinate(value):
        return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _coordinates_within_geofence(*, latitude, longitude, geofence):
        lat_diff = (Decimal(str(latitude)) - geofence.latitude) * Decimal("111320")
        lon_diff = (Decimal(str(longitude)) - geofence.longitude) * Decimal("111320")
        distance = (lat_diff ** 2 + lon_diff ** 2).sqrt()
        return distance <= Decimal(str(geofence.raio_metros))

    @staticmethod
    def _normalize_employee_ids(employee_ids):
        normalized_ids = set()
        for employee_id in employee_ids or []:
            if employee_id in (None, ""):
                continue
            try:
                normalized_ids.add(int(employee_id))
            except (TypeError, ValueError) as exc:
                raise ValidationError({"employees": "Selecione apenas colaboradores válidos."}) from exc
        return normalized_ids

    @staticmethod
    def _apply_employee_search(queryset, *, search):
        normalized_search = (search or "").strip()
        if not normalized_search:
            return queryset

        digits = "".join(ch for ch in normalized_search if ch.isdigit())
        query = Q(nome__icontains=normalized_search) | Q(
            matricula_interna__icontains=normalized_search
        )
        if digits:
            query |= Q(cpf__icontains=digits) | Q(pis__icontains=digits)
        return queryset.filter(query)


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
        time_clock=None,
        timestamp=None,
        origem=AttendanceRecord.Origem.ONLINE,
        client_event_id=None,
        latitude=None,
        longitude=None,
    ):
        self._validate_tipo(tipo)
        timestamp = timestamp or timezone.now()

        if time_clock is not None:
            TimeClockService().validate_attendance_prerequisites(
                time_clock=time_clock,
                employee=employee,
                latitude=latitude,
                longitude=longitude,
            )
        elif not employee.ativo:
            raise ValidationError("Funcionário inativo não pode registrar ponto.")

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

    def sincronizar_lote(self, tenant, registros, time_clock=None):
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
                time_clock=time_clock,
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
