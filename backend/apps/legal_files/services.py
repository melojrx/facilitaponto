import hashlib
import json

from django.utils import timezone

from .models import Comprovante


class ComprovanteService:
    def gerar(self, registro):
        local_ts = registro.timestamp.astimezone(timezone.get_current_timezone())
        conteudo = {
            "nome": registro.employee.nome,
            "pis": registro.employee.pis,
            "data": local_ts.strftime("%Y-%m-%d"),
            "hora": local_ts.strftime("%H:%M:%S"),
            "nsr": registro.nsr,
            "tipo": registro.tipo,
        }

        timestamp_carimbo = timezone.now()
        hash_carimbo = self._build_hash(conteudo, timestamp_carimbo)

        comprovante, _ = Comprovante.all_objects.update_or_create(
            registro=registro,
            defaults={
                "tenant": registro.tenant,
                "conteudo_json": conteudo,
                "timestamp_carimbo": timestamp_carimbo,
                "hash_carimbo": hash_carimbo,
            },
        )
        return comprovante

    @staticmethod
    def _build_hash(conteudo, timestamp_carimbo):
        payload = {
            "conteudo": conteudo,
            "timestamp_carimbo": timestamp_carimbo.isoformat(),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
