import base64

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


class AttendanceSyncItemSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(min_value=1)
    tipo = serializers.ChoiceField(choices=AttendanceRecord.Tipo.choices)
    timestamp = serializers.DateTimeField()
    client_event_id = serializers.CharField(max_length=100)
    imagem_base64 = serializers.CharField()
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

    def validate_client_event_id(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("client_event_id é obrigatório.")
        return normalized

    def validate_imagem_base64(self, value):
        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception as exc:
            raise serializers.ValidationError("imagem_base64 inválida.") from exc

        if not decoded:
            raise serializers.ValidationError("imagem_base64 não pode ser vazia.")
        return decoded


class AttendanceSyncSerializer(serializers.Serializer):
    registros = AttendanceSyncItemSerializer(many=True)

    def validate_registros(self, value):
        if not value:
            raise serializers.ValidationError("Informe ao menos um registro para sincronização.")

        timestamps = [item["timestamp"] for item in value]
        if timestamps != sorted(timestamps):
            raise serializers.ValidationError(
                "Registros offline devem ser enviados em ordem crescente de timestamp."
            )

        client_event_ids = [item["client_event_id"] for item in value]
        if len(client_event_ids) != len(set(client_event_ids)):
            raise serializers.ValidationError(
                "client_event_id duplicado no mesmo lote de sincronização."
            )

        return value


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
            "client_event_id",
            "foto_path",
            "foto_hash",
            "confianca_biometrica",
            "origem",
            "sincronizado_em",
        )
        read_only_fields = fields


class AttendanceSyncResultSerializer(serializers.Serializer):
    client_event_id = serializers.CharField()
    created = serializers.BooleanField()
    record = AttendanceRecordSerializer()
