import base64

from rest_framework import serializers

from .models import AttendanceAdjustment, AttendanceRecord, TimeClock, TimeClockGeofence


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


class TimeClockGeofenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeClockGeofence
        fields = (
            "id",
            "latitude",
            "longitude",
            "raio_metros",
            "ativo",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


class TimeClockDetailSerializer(serializers.ModelSerializer):
    tipo_rep = serializers.CharField(source="rep_badge_label", read_only=True)
    plataforma = serializers.CharField(source="get_plataforma_display", read_only=True)
    metodos_autenticacao = serializers.SerializerMethodField()
    codigo_ativacao = serializers.CharField(source="activation_code", read_only=True)
    colaboradores_total = serializers.IntegerField(read_only=True)
    cerca_virtual = serializers.SerializerMethodField()

    class Meta:
        model = TimeClock
        fields = (
            "id",
            "nome",
            "descricao",
            "tipo_rep",
            "plataforma",
            "status",
            "metodos_autenticacao",
            "codigo_ativacao",
            "colaboradores_total",
            "last_synced_at",
            "created_at",
            "updated_at",
            "cerca_virtual",
        )
        read_only_fields = fields

    def get_metodos_autenticacao(self, obj):
        return [obj.metodo_autenticacao]

    def get_cerca_virtual(self, obj):
        geofence = getattr(obj, "geofence", None)
        if geofence is None:
            return None
        return TimeClockGeofenceSerializer(geofence).data


class TimeClockUpdateSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=80)
    descricao = serializers.CharField(max_length=255, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=TimeClock.Status.choices)


class TimeClockActivationSerializer(serializers.Serializer):
    activation_code = serializers.CharField(max_length=6)
    device_id = serializers.CharField(max_length=100)
    nome_dispositivo = serializers.CharField(max_length=120, required=False, allow_blank=True)
    plataforma = serializers.ChoiceField(choices=TimeClock.Plataforma.choices)

    def validate_activation_code(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("activation_code é obrigatório.")
        return normalized

    def validate_device_id(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("device_id é obrigatório.")
        return normalized


class TimeClockEmployeeListQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)


class TimeClockEmployeeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    matricula = serializers.CharField()
    cpf = serializers.CharField()


class TimeClockEmployeeListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = TimeClockEmployeeSerializer(many=True)


class TimeClockEmployeeActionSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=500,
        required=False,
    )
    q = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get("employee_ids") and not attrs.get("q", "").strip():
            raise serializers.ValidationError(
                "Informe employee_ids ou um filtro q para a operação em lote."
            )
        return attrs


class TimeClockEmployeeActionResultSerializer(serializers.Serializer):
    moved_count = serializers.IntegerField(required=False)
    removed_count = serializers.IntegerField(required=False)
    ignored_count = serializers.IntegerField()
    disponiveis_count = serializers.IntegerField()
    no_relogio_count = serializers.IntegerField()


class TreatmentPointListQuerySerializer(serializers.Serializer):
    period = serializers.CharField(required=False, allow_blank=True)
    q = serializers.CharField(required=False, allow_blank=True)
    only_inconsistencies = serializers.BooleanField(required=False, default=False)
    only_pendencias = serializers.BooleanField(required=False, default=False)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)


class TreatmentPointEmployeeSummarySerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    nome = serializers.CharField()
    cargo = serializers.CharField()
    saldo_bh_min = serializers.IntegerField()
    he_50_min = serializers.IntegerField()
    he_100_min = serializers.IntegerField()
    atrasos_min = serializers.IntegerField()
    faltas_dias = serializers.IntegerField()
    pendencias_count = serializers.IntegerField()


class TreatmentPointEmployeeListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = TreatmentPointEmployeeSummarySerializer(many=True)


class TreatmentPointMirrorQuerySerializer(serializers.Serializer):
    period = serializers.CharField(required=False, allow_blank=True)


class TreatmentPointMirrorEmployeeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()
    cargo = serializers.CharField()


class TreatmentPointMirrorPeriodSerializer(serializers.Serializer):
    inicio = serializers.DateField()
    fim = serializers.DateField()
    status = serializers.CharField()


class TreatmentPointMirrorIndicatorsSerializer(serializers.Serializer):
    saldo_bh_min = serializers.IntegerField()
    he_50_min = serializers.IntegerField()
    he_100_min = serializers.IntegerField()
    atrasos_min = serializers.IntegerField()
    saidas_antecipadas_min = serializers.IntegerField()
    faltas_dias = serializers.IntegerField()
    adicional_noturno_min = serializers.IntegerField()
    total_trabalhado_min = serializers.IntegerField()
    total_previsto_min = serializers.IntegerField()


class TreatmentPointMirrorDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    date_label = serializers.CharField()
    weekday_label = serializers.CharField()
    expected_label = serializers.CharField()
    markings_label = serializers.CharField()
    worked_label = serializers.CharField()
    balance_label = serializers.CharField()
    occurrences = serializers.ListField(child=serializers.CharField())
    row_tone = serializers.CharField()
    pending_adjustments = serializers.ListField(child=serializers.DictField(), required=False)


class TreatmentPointMirrorSerializer(serializers.Serializer):
    employee = TreatmentPointMirrorEmployeeSerializer()
    periodo = TreatmentPointMirrorPeriodSerializer()
    indicadores = TreatmentPointMirrorIndicatorsSerializer()
    dias = TreatmentPointMirrorDaySerializer(many=True)


class TreatmentPointDayAdjustmentSerializer(serializers.Serializer):
    acao = serializers.CharField()
    hora = serializers.RegexField(regex=r"^\d{2}:\d{2}$")
    motivo = serializers.CharField(max_length=255)
    tipo = serializers.ChoiceField(choices=AttendanceRecord.Tipo.choices, required=False)


class TreatmentPointDayAdjustmentResultSerializer(serializers.Serializer):
    ajuste_id = serializers.CharField()
    status = serializers.CharField()
    date = serializers.DateField()


class TreatmentPointAdjustmentDecisionSerializer(serializers.Serializer):
    decisao = serializers.ChoiceField(choices=("APROVAR", "REJEITAR", "DESCONSIDERAR"))
    observacao = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class TreatmentPointAdjustmentDecisionResultSerializer(serializers.Serializer):
    ajuste_id = serializers.CharField()
    status = serializers.ChoiceField(choices=AttendanceAdjustment.Status.choices)
    decidido_em = serializers.DateTimeField()
    observacao = serializers.CharField()


class AdjustmentRequestSummarySerializer(serializers.Serializer):
    pendentes = serializers.IntegerField()
    total_abertas = serializers.IntegerField()


class RequestSummarySerializer(serializers.Serializer):
    ajustes = AdjustmentRequestSummarySerializer()
    acessos = AdjustmentRequestSummarySerializer()


class AdjustmentRequestListQuerySerializer(serializers.Serializer):
    status = serializers.CharField(required=False, allow_blank=True)
    periodo_inicio = serializers.DateField(required=False)
    periodo_fim = serializers.DateField(required=False)
    employee_id = serializers.IntegerField(required=False, min_value=1)
    q = serializers.CharField(required=False, allow_blank=True)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)

    def validate(self, attrs):
        start = attrs.get("periodo_inicio")
        end = attrs.get("periodo_fim")
        if start and end and start > end:
            raise serializers.ValidationError("Informe um período válido.")
        return attrs


class AdjustmentRequestListItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    protocolo = serializers.CharField()
    employee_id = serializers.IntegerField()
    colaborador_nome = serializers.CharField()
    data_referencia = serializers.DateField()
    tipo_ajuste = serializers.CharField()
    motivo = serializers.CharField()
    status = serializers.CharField()
    solicitado_em = serializers.DateTimeField()


class AdjustmentRequestListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = AdjustmentRequestListItemSerializer(many=True)


class AdjustmentRequestHistoryItemSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    usuario = serializers.CharField(allow_blank=True)
    data = serializers.DateTimeField(allow_null=True)
    observacao = serializers.CharField(allow_blank=True)


class AdjustmentRequestDetailSerializer(serializers.Serializer):
    id = serializers.CharField()
    protocolo = serializers.CharField()
    status = serializers.CharField()
    marcacoes_originais = serializers.ListField(child=serializers.CharField())
    marcacoes_propostas = serializers.ListField(child=serializers.CharField())
    historico = AdjustmentRequestHistoryItemSerializer(many=True)


class TreatmentPointAutoAdjustSerializer(serializers.Serializer):
    periodo_inicio = serializers.DateField()
    periodo_fim = serializers.DateField()

    def validate(self, attrs):
        if attrs["periodo_inicio"] > attrs["periodo_fim"]:
            raise serializers.ValidationError("Informe um período válido.")
        if (
            attrs["periodo_inicio"].year != attrs["periodo_fim"].year
            or attrs["periodo_inicio"].month != attrs["periodo_fim"].month
        ):
            raise serializers.ValidationError("O ajuste automático do MVP suporta apenas um único mês por vez.")
        return attrs


class TreatmentPointAutoAdjustResultSerializer(serializers.Serializer):
    processed_days = serializers.IntegerField()
    updated_days = serializers.IntegerField()
    pendencias_restantes = serializers.IntegerField()
