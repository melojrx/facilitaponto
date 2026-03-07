from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsDeviceToken

from .models import Employee
from .serializers import EmployeeActiveSerializer


class ActiveEmployeesView(generics.ListAPIView):
    """Lista funcionários ativos do tenant autenticado para sincronização do tablet."""

    permission_classes = [IsAuthenticated, IsDeviceToken]
    serializer_class = EmployeeActiveSerializer

    def get_queryset(self):
        return Employee.objects.filter(ativo=True).order_by("nome")
