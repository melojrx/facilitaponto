"""
Roteamento central da API REST.
Cada app registra suas próprias rotas aqui via include().
"""
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import DeviceRegisterView, TenantTokenObtainPairView

urlpatterns = [
    # Autenticação JWT
    path("auth/token/", TenantTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/device/register/", DeviceRegisterView.as_view(), name="device_register"),
    # Apps — serão adicionados à medida que os apps forem implementados
    # path("tenants/", include("apps.tenants.urls")),
    path("employees/", include("apps.employees.urls")),
    # path("attendance/", include("apps.attendance.urls")),
]
