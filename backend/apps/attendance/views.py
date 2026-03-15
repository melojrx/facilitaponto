import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Device, User
from apps.accounts.permissions import CanDecideAdjustmentRequests, IsDeviceToken, IsTenantMember
from apps.employees.models import Employee
from apps.legal_files.serializers import ComprovanteSerializer
from apps.legal_files.services import ComprovanteService

from .models import AttendanceAdjustment, AttendanceRecord, TimeClock
from .serializers import (
    AttendanceRecordSerializer,
    AttendanceRegisterSerializer,
    AttendanceSyncResultSerializer,
    AttendanceSyncSerializer,
    AdjustmentRequestDetailSerializer,
    AdjustmentRequestListQuerySerializer,
    AdjustmentRequestListSerializer,
    RequestSummarySerializer,
    TreatmentPointAutoAdjustResultSerializer,
    TreatmentPointAutoAdjustSerializer,
    TreatmentPointAdjustmentDecisionResultSerializer,
    TreatmentPointAdjustmentDecisionSerializer,
    TreatmentPointDayAdjustmentResultSerializer,
    TreatmentPointDayAdjustmentSerializer,
    TreatmentPointEmployeeListSerializer,
    TreatmentPointListQuerySerializer,
    TreatmentPointMirrorQuerySerializer,
    TreatmentPointMirrorSerializer,
    TimeClockActivationSerializer,
    TimeClockDetailSerializer,
    TimeClockEmployeeActionResultSerializer,
    TimeClockEmployeeActionSerializer,
    TimeClockEmployeeListQuerySerializer,
    TimeClockEmployeeListSerializer,
    TimeClockGeofenceSerializer,
    TimeClockUpdateSerializer,
)
from .services import AttendanceService, TimeClockService
from .treatment import TreatmentPointService, parse_treatment_period


def _get_time_clock_for_tenant_or_404(*, tenant, time_clock_id):
    return get_object_or_404(
        TimeClock.all_objects.select_related(
            "geofence",
            "current_device",
        ),
        tenant=tenant,
        id=time_clock_id,
    )


class AttendanceRegisterView(APIView):
    """Registra batida de ponto online a partir do app mobile."""

    permission_classes = [IsAuthenticated, IsDeviceToken]

    def post(self, request):
        serializer = AttendanceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device_pk = request.auth.get("device_pk")
        device = get_object_or_404(Device.objects.filter(tenant=request.tenant), id=device_pk)
        time_clock = TimeClockService().get_time_clock_for_device(
            tenant=request.tenant,
            device=device,
        )
        employee = get_object_or_404(
            Employee.objects.filter(ativo=True),
            id=serializer.validated_data["employee_id"],
        )
        imagem_bytes = serializer.validated_data["imagem"].read()

        try:
            record, _ = AttendanceService().registrar(
                employee=employee,
                tipo=serializer.validated_data["tipo"],
                imagem_bytes=imagem_bytes,
                time_clock=time_clock,
                timestamp=serializer.validated_data.get("timestamp"),
                origem=serializer.validated_data.get("origem", "online"),
                latitude=serializer.validated_data.get("latitude"),
                longitude=serializer.validated_data.get("longitude"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class AttendanceSyncView(APIView):
    """Sincroniza lote de registros offline com idempotência por client_event_id."""

    permission_classes = [IsAuthenticated, IsDeviceToken]

    def post(self, request):
        serializer = AttendanceSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device_pk = request.auth.get("device_pk")
        device = get_object_or_404(Device.objects.filter(tenant=request.tenant), id=device_pk)
        time_clock = TimeClockService().get_time_clock_for_device(
            tenant=request.tenant,
            device=device,
        )
        try:
            results = AttendanceService().sincronizar_lote(
                tenant=request.tenant,
                registros=serializer.validated_data["registros"],
                time_clock=time_clock,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        payload = AttendanceSyncResultSerializer(results, many=True).data
        return Response({"results": payload}, status=status.HTTP_200_OK)


class AttendanceComprovanteView(APIView):
    """Retorna comprovante de um registro de ponto."""

    permission_classes = [IsAuthenticated, IsDeviceToken]

    def get(self, request, record_id):
        record = get_object_or_404(AttendanceRecord.objects, id=record_id)
        comprovante = getattr(record, "comprovante", None)
        if comprovante is None:
            comprovante = ComprovanteService().gerar(record)

        return Response(ComprovanteSerializer(comprovante).data, status=status.HTTP_200_OK)


class TimeClockDetailApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, time_clock_id):
        time_clock = _get_time_clock_for_tenant_or_404(
            tenant=request.tenant,
            time_clock_id=time_clock_id,
        )
        payload = TimeClockDetailSerializer(time_clock).data
        return Response(payload, status=status.HTTP_200_OK)

    def patch(self, request, time_clock_id):
        time_clock = _get_time_clock_for_tenant_or_404(
            tenant=request.tenant,
            time_clock_id=time_clock_id,
        )
        serializer = TimeClockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = TimeClockService().update_time_clock(
                time_clock=time_clock,
                nome=serializer.validated_data["nome"],
                descricao=serializer.validated_data.get("descricao", ""),
                status=serializer.validated_data["status"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc

        return Response(
            TimeClockDetailSerializer(updated).data,
            status=status.HTTP_200_OK,
        )


class TimeClockGeofenceApiView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, time_clock_id):
        time_clock = _get_time_clock_for_tenant_or_404(
            tenant=request.tenant,
            time_clock_id=time_clock_id,
        )
        serializer = TimeClockGeofenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            geofence = TimeClockService().configure_geofence(
                time_clock=time_clock,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc

        return Response(TimeClockGeofenceSerializer(geofence).data, status=status.HTTP_200_OK)

    def patch(self, request, time_clock_id):
        time_clock = _get_time_clock_for_tenant_or_404(
            tenant=request.tenant,
            time_clock_id=time_clock_id,
        )
        if request.data.get("ativo") is False:
            geofence = TimeClockService().disable_geofence(time_clock=time_clock)
            if geofence is None:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(TimeClockGeofenceSerializer(geofence).data, status=status.HTTP_200_OK)
        return self.put(request, time_clock_id)

    def delete(self, request, time_clock_id):
        time_clock = _get_time_clock_for_tenant_or_404(
            tenant=request.tenant,
            time_clock_id=time_clock_id,
        )
        TimeClockService().disable_geofence(time_clock=time_clock)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TimeClockActivationApiView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TimeClockActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            time_clock, device = TimeClockService().activate_time_clock(
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            status_code = status.HTTP_400_BAD_REQUEST
            if "Relógio indisponível para ativação no momento." in exc.messages:
                status_code = status.HTTP_409_CONFLICT
            if hasattr(exc, "message_dict") and "activation_code" in exc.message_dict:
                status_code = status.HTTP_404_NOT_FOUND
            return Response(detail, status=status_code)

        actor = (
            User.objects.filter(tenant=time_clock.tenant, is_account_owner=True).first()
            or User.objects.filter(tenant=time_clock.tenant, is_active=True).order_by("created_at").first()
        )
        if actor is None:
            return Response(
                {"detail": "Tenant sem usuário elegível para emissão do token de dispositivo."},
                status=status.HTTP_409_CONFLICT,
            )
        refresh = RefreshToken.for_user(actor)
        refresh["tenant_id"] = str(time_clock.tenant_id)
        refresh["role"] = "device"
        refresh["is_device"] = True
        refresh["device_id"] = device.device_id
        refresh["device_pk"] = str(device.id)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "relogio": TimeClockDetailSerializer(time_clock).data,
                "device": {
                    "id": str(device.id),
                    "device_id": device.device_id,
                    "nome": device.nome,
                    "ativo": device.ativo,
                },
            },
            status=status.HTTP_200_OK,
        )


class _TimeClockEmployeeListBaseView(APIView):
    permission_classes = [IsAuthenticated]
    queryset_factory_name = ""

    def get(self, request, time_clock_id):
        time_clock = _get_time_clock_for_tenant_or_404(
            tenant=request.tenant,
            time_clock_id=time_clock_id,
        )
        serializer = TimeClockEmployeeListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        queryset = getattr(TimeClockService(), self.queryset_factory_name)(
            time_clock=time_clock,
            search=serializer.validated_data.get("q", ""),
        )
        results = [
            {
                "id": employee.id,
                "nome": employee.nome,
                "matricula": employee.matricula_interna or "-",
                "cpf": employee.cpf,
            }
            for employee in queryset
        ]
        payload = TimeClockEmployeeListSerializer(
            {"count": len(results), "results": results}
        ).data
        return Response(payload, status=status.HTTP_200_OK)


class TimeClockAvailableEmployeesApiView(_TimeClockEmployeeListBaseView):
    queryset_factory_name = "available_employees_queryset"


class TimeClockAssignedEmployeesApiView(_TimeClockEmployeeListBaseView):
    queryset_factory_name = "assigned_employees_queryset"


class _TimeClockEmployeeActionBaseView(APIView):
    permission_classes = [IsAuthenticated]
    action_name = ""

    def post(self, request, time_clock_id):
        time_clock = _get_time_clock_for_tenant_or_404(
            tenant=request.tenant,
            time_clock_id=time_clock_id,
        )
        serializer = TimeClockEmployeeActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = TimeClockService()

        try:
            if self.action_name == "assign_all_employees":
                result_total = service.assign_all_employees(
                    time_clock=time_clock,
                    search=serializer.validated_data.get("q", ""),
                )
            elif self.action_name == "remove_all_employees":
                result_total = service.remove_all_employees(
                    time_clock=time_clock,
                    search=serializer.validated_data.get("q", ""),
                )
            elif self.action_name == "assign_employees":
                result_total = service.assign_employees(
                    time_clock=time_clock,
                    employee_ids=serializer.validated_data.get("employee_ids"),
                )
            else:
                result_total = service.remove_employees(
                    time_clock=time_clock,
                    employee_ids=serializer.validated_data.get("employee_ids"),
                )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc

        payload = {
            "ignored_count": 0,
            "disponiveis_count": service.available_employees_queryset(time_clock=time_clock).count(),
            "no_relogio_count": service.assigned_employees_queryset(time_clock=time_clock).count(),
        }
        if "assign" in self.action_name:
            payload["moved_count"] = result_total
        else:
            payload["removed_count"] = result_total
        return Response(TimeClockEmployeeActionResultSerializer(payload).data, status=status.HTTP_200_OK)


class TimeClockAssignSelectedApiView(_TimeClockEmployeeActionBaseView):
    action_name = "assign_employees"


class TimeClockAssignAllApiView(_TimeClockEmployeeActionBaseView):
    action_name = "assign_all_employees"


class TimeClockRemoveSelectedApiView(_TimeClockEmployeeActionBaseView):
    action_name = "remove_employees"


class TimeClockRemoveAllApiView(_TimeClockEmployeeActionBaseView):
    action_name = "remove_all_employees"


class TreatmentPointEmployeeListApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = TreatmentPointListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        try:
            period = parse_treatment_period(serializer.validated_data.get("period"))
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        summaries = TreatmentPointService().list_collaborator_summaries(
            tenant=request.tenant,
            period=period,
            search=serializer.validated_data.get("q", ""),
            only_inconsistencies=serializer.validated_data.get("only_inconsistencies", False),
            only_pendencias=serializer.validated_data.get("only_pendencias", False),
        )

        page = serializer.validated_data.get("page", 1)
        page_size = serializer.validated_data.get("page_size", 20)
        start = (page - 1) * page_size
        end = start + page_size
        payload = {
            "count": len(summaries),
            "results": summaries[start:end],
        }
        return Response(TreatmentPointEmployeeListSerializer(payload).data, status=status.HTTP_200_OK)


class TreatmentPointMirrorApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        serializer = TreatmentPointMirrorQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        try:
            period = parse_treatment_period(serializer.validated_data.get("period"))
            mirror = TreatmentPointService().build_employee_mirror(
                tenant=request.tenant,
                employee_id=employee_id,
                period=period,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except Employee.DoesNotExist:
            return Response({"detail": "Colaborador não encontrado para este tenant."}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "employee": {
                "id": mirror["employee_id"],
                "nome": mirror["nome"],
                "cargo": mirror["cargo"],
            },
            "periodo": {
                "inicio": period.start_date,
                "fim": period.end_date,
                "status": "ABERTO",
            },
            "indicadores": {
                "saldo_bh_min": mirror["saldo_bh_min"],
                "he_50_min": mirror["he_50_min"],
                "he_100_min": mirror["he_100_min"],
                "atrasos_min": mirror["atrasos_min"],
                "saidas_antecipadas_min": mirror["saidas_antec_min"],
                "faltas_dias": mirror["faltas_dias"],
                "adicional_noturno_min": mirror["adicional_noturno_min"],
                "total_trabalhado_min": mirror["total_trabalhado_min"],
                "total_previsto_min": mirror["total_previsto_min"],
            },
            "dias": mirror["daily_rows"],
        }
        return Response(TreatmentPointMirrorSerializer(payload).data, status=status.HTTP_200_OK)


class TreatmentPointDayAdjustmentApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id, date):
        serializer = TreatmentPointDayAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            target_date = datetime.date.fromisoformat(date)
            adjustment = TreatmentPointService().create_day_adjustment(
                tenant=request.tenant,
                employee_id=employee_id,
                target_date=target_date,
                action=serializer.validated_data["acao"],
                hour=serializer.validated_data["hora"],
                motivo=serializer.validated_data["motivo"],
                requested_by=request.user,
                tipo=serializer.validated_data.get("tipo"),
            )
        except ValueError as exc:
            raise ValidationError(["Dados de marcação inválidos para este dia."]) from exc
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except Employee.DoesNotExist:
            return Response({"detail": "Colaborador não encontrado para este tenant."}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "ajuste_id": str(adjustment.id),
            "status": adjustment.status,
            "date": target_date,
        }
        return Response(TreatmentPointDayAdjustmentResultSerializer(payload).data, status=status.HTTP_201_CREATED)


class TreatmentPointAutoAdjustApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        serializer = TreatmentPointAutoAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        period = parse_treatment_period(
            f"{serializer.validated_data['periodo_inicio'].year:04d}-{serializer.validated_data['periodo_inicio'].month:02d}"
        )
        try:
            result = TreatmentPointService().auto_adjust_period(
                tenant=request.tenant,
                employee_id=employee_id,
                period=period,
                requested_by=request.user,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except Employee.DoesNotExist:
            return Response({"detail": "Colaborador não encontrado para este tenant."}, status=status.HTTP_404_NOT_FOUND)

        return Response(TreatmentPointAutoAdjustResultSerializer(result).data, status=status.HTTP_200_OK)


class TreatmentPointAdjustmentDecisionApiView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, CanDecideAdjustmentRequests]

    def post(self, request, employee_id, adjustment_id):
        serializer = TreatmentPointAdjustmentDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            mirror = TreatmentPointService().build_employee_mirror(
                tenant=request.tenant,
                employee_id=employee_id,
                period=parse_treatment_period(request.query_params.get("period")),
            )
            known_pending_ids = {
                item["id"]
                for row in mirror["daily_rows"]
                for item in row.get("pending_adjustments", [])
            }
            if str(adjustment_id) not in known_pending_ids:
                return Response(
                    {"detail": "Ajuste pendente não encontrado para este colaborador."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            adjustment = TreatmentPointService().decide_adjustment(
                tenant=request.tenant,
                adjustment_id=adjustment_id,
                decision=serializer.validated_data["decisao"],
                decided_by=request.user,
                decision_note=serializer.validated_data.get("observacao", ""),
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        except Employee.DoesNotExist:
            return Response({"detail": "Colaborador não encontrado para este tenant."}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "ajuste_id": str(adjustment.id),
            "status": adjustment.status,
            "decidido_em": adjustment.decided_at,
            "observacao": adjustment.decision_note,
        }
        return Response(TreatmentPointAdjustmentDecisionResultSerializer(payload).data, status=status.HTTP_200_OK)


class RequestSummaryApiView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request):
        payload = TreatmentPointService().adjustment_requests_summary(tenant=request.tenant)
        return Response(RequestSummarySerializer(payload).data, status=status.HTTP_200_OK)


class AdjustmentRequestListApiView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request):
        serializer = AdjustmentRequestListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        results = TreatmentPointService().list_adjustment_requests(
            tenant=request.tenant,
            status_value=serializer.validated_data.get("status", ""),
            period_start=serializer.validated_data.get("periodo_inicio"),
            period_end=serializer.validated_data.get("periodo_fim"),
            employee_id=serializer.validated_data.get("employee_id"),
            query=serializer.validated_data.get("q", ""),
        )
        page = serializer.validated_data.get("page", 1)
        page_size = serializer.validated_data.get("page_size", 20)
        start = (page - 1) * page_size
        end = start + page_size
        payload = {"count": len(results), "results": results[start:end]}
        return Response(AdjustmentRequestListSerializer(payload).data, status=status.HTTP_200_OK)


class AdjustmentRequestDetailApiView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request, adjustment_id):
        try:
            payload = TreatmentPointService().get_adjustment_request_detail(
                tenant=request.tenant,
                adjustment_id=adjustment_id,
            )
        except AttendanceAdjustment.DoesNotExist:
            return Response({"detail": "Solicitação não encontrada para este tenant."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response(AdjustmentRequestDetailSerializer(payload).data, status=status.HTTP_200_OK)


class AdjustmentRequestDecisionApiView(APIView):
    permission_classes = [IsAuthenticated, IsTenantMember, CanDecideAdjustmentRequests]

    def post(self, request, adjustment_id):
        serializer = TreatmentPointAdjustmentDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            adjustment = TreatmentPointService().decide_adjustment(
                tenant=request.tenant,
                adjustment_id=adjustment_id,
                decision=serializer.validated_data["decisao"],
                decided_by=request.user,
                decision_note=serializer.validated_data.get("observacao", ""),
            )
        except AttendanceAdjustment.DoesNotExist:
            return Response({"detail": "Solicitação não encontrada para este tenant."}, status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as exc:
            error_messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
            conflict_errors = {
                "Não é permitido decidir um ajuste já finalizado.",
            }
            if any(message in conflict_errors for message in error_messages):
                return Response({"detail": error_messages[0]}, status=status.HTTP_409_CONFLICT)
            raise ValidationError(error_messages) from exc

        payload = {
            "ajuste_id": str(adjustment.id),
            "status": adjustment.status,
            "decidido_em": adjustment.decided_at,
            "observacao": adjustment.decision_note,
        }
        return Response(TreatmentPointAdjustmentDecisionResultSerializer(payload).data, status=status.HTTP_200_OK)
