from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsDeviceToken
from apps.employees.models import Employee
from apps.legal_files.serializers import ComprovanteSerializer
from apps.legal_files.services import ComprovanteService

from .models import AttendanceRecord
from .serializers import AttendanceRecordSerializer, AttendanceRegisterSerializer
from .services import AttendanceService


class AttendanceRegisterView(APIView):
    """Registra batida de ponto online a partir do app mobile."""

    permission_classes = [IsAuthenticated, IsDeviceToken]

    def post(self, request):
        serializer = AttendanceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = get_object_or_404(
            Employee.objects.filter(ativo=True),
            id=serializer.validated_data["employee_id"],
        )
        imagem_bytes = serializer.validated_data["imagem"].read()

        try:
            record = AttendanceService().registrar(
                employee=employee,
                tipo=serializer.validated_data["tipo"],
                imagem_bytes=imagem_bytes,
                timestamp=serializer.validated_data.get("timestamp"),
                origem=serializer.validated_data.get("origem", "online"),
                latitude=serializer.validated_data.get("latitude"),
                longitude=serializer.validated_data.get("longitude"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class AttendanceComprovanteView(APIView):
    """Retorna comprovante de um registro de ponto."""

    permission_classes = [IsAuthenticated, IsDeviceToken]

    def get(self, request, record_id):
        record = get_object_or_404(AttendanceRecord.objects, id=record_id)
        comprovante = getattr(record, "comprovante", None)
        if comprovante is None:
            comprovante = ComprovanteService().gerar(record)

        return Response(ComprovanteSerializer(comprovante).data, status=status.HTTP_200_OK)
