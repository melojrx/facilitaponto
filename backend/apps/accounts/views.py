"""Views do app accounts."""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Device
from .permissions import IsTenantMember
from .serializers import DeviceRegisterSerializer, TenantTokenObtainPairSerializer


class TenantTokenObtainPairView(TokenObtainPairView):
    """Endpoint JWT que inclui tenant_id no token quando disponível."""

    serializer_class = TenantTokenObtainPairSerializer


class DeviceRegisterView(APIView):
    """Registra/atualiza device do tenant e retorna JWT de dispositivo."""

    permission_classes = [IsAuthenticated, IsTenantMember]

    def post(self, request):
        serializer = DeviceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = request.tenant
        device_id = serializer.validated_data["device_id"]

        device, created = Device.objects.update_or_create(
            tenant=tenant,
            device_id=device_id,
            defaults={
                "nome": serializer.validated_data.get("nome", ""),
                "ativo": True,
                "last_seen_at": timezone.now(),
            },
        )

        refresh = RefreshToken.for_user(request.user)
        refresh["tenant_id"] = str(tenant.id)
        refresh["role"] = "device"
        refresh["is_device"] = True
        refresh["device_id"] = device.device_id
        refresh["device_pk"] = str(device.id)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "device": {
                    "id": str(device.id),
                    "device_id": device.device_id,
                    "nome": device.nome,
                    "ativo": device.ativo,
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
