"""Views do app accounts."""

from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import TenantTokenObtainPairSerializer


class TenantTokenObtainPairView(TokenObtainPairView):
    """Endpoint JWT que inclui tenant_id no token quando disponível."""

    serializer_class = TenantTokenObtainPairSerializer
