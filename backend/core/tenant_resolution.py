"""Resolução centralizada de tenant para web e API."""

import logging
import uuid

from django.db.models import Q
from rest_framework_simplejwt.tokens import AccessToken

from apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


def resolve_tenant_from_jwt(auth_header: str):
    """Resolve tenant ativo a partir do header Authorization Bearer."""
    if not auth_header.startswith("Bearer "):
        return None

    token_str = auth_header.split(" ", 1)[1]
    try:
        token = AccessToken(token_str)
        tenant_id = token.get("tenant_id")
        if not tenant_id:
            return None
        return Tenant.objects.filter(id=tenant_id, ativo=True).first()
    except Exception as exc:
        logger.debug("Falha ao resolver tenant via JWT: %s", exc.__class__.__name__, exc_info=True)
        return None


def resolve_tenant_from_user(user):
    """Resolve tenant ativo a partir do usuário autenticado sem side effects."""
    if not user or not getattr(user, "is_authenticated", False):
        return None

    tenant_id = getattr(user, "tenant_id", None)
    if tenant_id:
        return Tenant.objects.filter(id=tenant_id, ativo=True).first()

    query = Q()
    email = getattr(user, "email", "")
    cpf = getattr(user, "cpf", "")

    if email:
        query |= Q(email_contato__iexact=email)
    if cpf:
        query |= Q(documento=cpf) | Q(cnpj=cpf) | Q(responsavel_cpf=cpf)

    if not query:
        return None

    candidates = Tenant.objects.filter(query, ativo=True).distinct()
    if candidates.count() != 1:
        return None

    return candidates.first()


def resolve_tenant_from_host(host: str):
    """Resolve tenant ativo a partir do subdomínio (UUID ou CNPJ)."""
    host_without_port = host.split(":", 1)[0].strip().lower()
    if not host_without_port:
        return None

    host_parts = host_without_port.split(".")
    if len(host_parts) < 3:
        return None

    subdomain = host_parts[0]
    if subdomain in {"www", "api"}:
        return None

    if subdomain.isdigit():
        return Tenant.objects.filter(cnpj=subdomain, ativo=True).first()

    try:
        tenant_uuid = uuid.UUID(subdomain)
    except ValueError:
        return None

    return Tenant.objects.filter(id=tenant_uuid, ativo=True).first()


def resolve_tenant_for_request(request):
    """
    Resolve tenant do request com estratégia unificada para web e API.

    Ordem:
    1. JWT (quando presente)
    2. Usuário autenticado (vínculo direto ou heurística sem persistência)
    3. Subdomínio
    """
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    tenant = resolve_tenant_from_jwt(auth_header)
    if tenant is not None:
        return tenant

    tenant = resolve_tenant_from_user(getattr(request, "user", None))
    if tenant is not None:
        return tenant

    return resolve_tenant_from_host(request.META.get("HTTP_HOST", ""))
