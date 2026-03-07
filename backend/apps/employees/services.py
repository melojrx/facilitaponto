from django.db import transaction

from .models import NSRSequence


def get_next_nsr(tenant_id):
    """
    Gera próximo NSR de forma atômica por tenant.

    O lock pessimista (`select_for_update`) impede colisão em requests concorrentes.
    """
    with transaction.atomic():
        sequence, _ = NSRSequence.all_objects.select_for_update().get_or_create(
            tenant_id=tenant_id,
            defaults={"ultimo_nsr": 0},
        )
        sequence.ultimo_nsr += 1
        sequence.save(update_fields=["ultimo_nsr", "updated_at"])
        return sequence.ultimo_nsr
