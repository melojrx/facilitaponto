from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Device, User
from apps.accounts.permissions import IsDeviceToken
from apps.employees.models import Employee
from apps.legal_files.serializers import ComprovanteSerializer
from apps.legal_files.services import ComprovanteService

from .models import AttendanceRecord, TimeClock
from .serializers import (
    AttendanceRecordSerializer,
    AttendanceRegisterSerializer,
    AttendanceSyncResultSerializer,
    AttendanceSyncSerializer,
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
