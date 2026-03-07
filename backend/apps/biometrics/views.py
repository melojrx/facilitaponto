from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsDeviceToken, IsTenantMember
from apps.employees.models import Employee

from .models import ConsentimentoBiometrico, FacialEmbedding
from .serializers import (
    ConsentimentoBiometricoCreateSerializer,
    ConsentimentoBiometricoSerializer,
    EmployeeEmbeddingCacheSerializer,
    EnrollBiometricoSerializer,
    FacialEmbeddingSerializer,
    VerificacaoBiometricaSerializer,
    VerifyBiometricoSerializer,
)
from .services import BiometriaService


class EmployeeConsentView(APIView):
    """Registra consentimento biométrico do funcionário (pré-requisito LGPD)."""

    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, employee_id):
        serializer = ConsentimentoBiometricoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = get_object_or_404(Employee.objects, id=employee_id)
        consent = ConsentimentoBiometrico.objects.create(
            employee=employee,
            aceito=serializer.validated_data["aceito"],
            versao_termo=serializer.validated_data["versao_termo"],
            ip_origem=self._get_client_ip(request),
        )

        return Response(
            ConsentimentoBiometricoSerializer(consent).data,
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip() or None
        return request.META.get("REMOTE_ADDR")


class EmployeeEnrollView(APIView):
    """Realiza cadastro de embedding facial do funcionário (exige consentimento ativo)."""

    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request, employee_id):
        serializer = EnrollBiometricoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = get_object_or_404(Employee.objects, id=employee_id)
        imagem_bytes = serializer.validated_data["imagem"].read()

        try:
            embedding = BiometriaService().cadastrar_embedding(employee, imagem_bytes)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(
            FacialEmbeddingSerializer(embedding).data,
            status=status.HTTP_201_CREATED,
        )


class BiometricVerifyView(APIView):
    """Verifica biometria do funcionário para registro de ponto no app mobile."""

    permission_classes = [IsAuthenticated, IsDeviceToken]

    def post(self, request):
        serializer = VerifyBiometricoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee_id = serializer.validated_data["employee_id"]
        employee = get_object_or_404(Employee.objects.filter(ativo=True), id=employee_id)
        imagem_bytes = serializer.validated_data["imagem"].read()

        try:
            result = BiometriaService().verificar(employee, imagem_bytes)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(VerificacaoBiometricaSerializer(result).data, status=status.HTTP_200_OK)


class EmployeeEmbeddingsView(generics.ListAPIView):
    """Retorna embeddings ativos (criptografados) para cache local do tablet."""

    permission_classes = [IsAuthenticated, IsDeviceToken]
    serializer_class = EmployeeEmbeddingCacheSerializer

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return FacialEmbedding.objects.none()

        return (
            FacialEmbedding.objects.filter(
                employee__tenant=tenant,
                employee__ativo=True,
                ativo=True,
            )
            .select_related("employee")
            .order_by("employee_id")
        )
