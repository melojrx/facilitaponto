import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ValidationError


class AttendancePhotoStorageService:
    def __init__(self, client=None):
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name="us-east-1",
        )

    def upload_attendance_photo(
        self,
        tenant_id,
        timestamp,
        foto_hash,
        imagem_bytes,
        content_type="image/jpeg",
    ):
        key = self.build_object_key(tenant_id=tenant_id, timestamp=timestamp, foto_hash=foto_hash)
        self._ensure_bucket_exists()

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=imagem_bytes,
                ContentType=content_type,
            )
        except ClientError as exc:
            raise ValidationError("Falha ao salvar foto do registro no storage.") from exc

        return f"s3://{self.bucket}/{key}"

    def _ensure_bucket_exists(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                raise ValidationError("Falha ao acessar bucket do storage.") from exc

        try:
            self.client.create_bucket(Bucket=self.bucket)
        except ClientError as exc:
            raise ValidationError("Falha ao criar bucket do storage.") from exc

    @staticmethod
    def build_object_key(tenant_id, timestamp, foto_hash):
        day = timestamp.strftime("%Y/%m/%d")
        return f"attendance/{tenant_id}/{day}/{foto_hash}.jpg"
