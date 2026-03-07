from rest_framework import serializers

from .models import AttendanceRecord


class AttendanceRegisterSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(min_value=1)
    tipo = serializers.ChoiceField(choices=AttendanceRecord.Tipo.choices)
    imagem = serializers.ImageField()
    timestamp = serializers.DateTimeField(required=False)
    origem = serializers.ChoiceField(
        choices=AttendanceRecord.Origem.choices,
        required=False,
        default=AttendanceRecord.Origem.ONLINE,
    )
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
    )


class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = (
            "id",
            "tenant_id",
            "employee_id",
            "tipo",
            "timestamp",
            "nsr",
            "foto_path",
            "foto_hash",
            "confianca_biometrica",
            "origem",
            "sincronizado_em",
        )
        read_only_fields = fields
