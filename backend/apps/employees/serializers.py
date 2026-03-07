from rest_framework import serializers

from .models import Employee


class EmployeeActiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ("id", "nome", "pis")
