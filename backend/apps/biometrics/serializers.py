import base64

from rest_framework import serializers

from .models import ConsentimentoBiometrico, FacialEmbedding


class ConsentimentoBiometricoCreateSerializer(serializers.Serializer):
    aceito = serializers.BooleanField()
    versao_termo = serializers.CharField(max_length=20)


class ConsentimentoBiometricoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentimentoBiometrico
        fields = ("id", "employee", "timestamp", "aceito", "ip_origem", "versao_termo")
        read_only_fields = fields


class EnrollBiometricoSerializer(serializers.Serializer):
    imagem = serializers.ImageField()


class VerifyBiometricoSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField(min_value=1)
    imagem = serializers.ImageField()


class VerificacaoBiometricaSerializer(serializers.Serializer):
    autenticado = serializers.BooleanField()
    distancia = serializers.FloatField()
    threshold = serializers.FloatField()


class FacialEmbeddingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacialEmbedding
        fields = ("id", "employee", "created_at", "ativo")
        read_only_fields = fields


class EmployeeEmbeddingCacheSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(read_only=True)
    updated_at = serializers.DateTimeField(source="created_at", read_only=True)
    embedding_encrypted = serializers.SerializerMethodField()

    class Meta:
        model = FacialEmbedding
        fields = ("employee_id", "embedding_encrypted", "updated_at")
        read_only_fields = fields

    def get_embedding_encrypted(self, obj):
        data = obj.embedding_data
        if isinstance(data, memoryview):
            data = data.tobytes()
        return base64.b64encode(data).decode("ascii")
