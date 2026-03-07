"""
Tenant context utilities.

Stores the active tenant for the current request/task execution context.
This allows tenant-aware managers to filter data automatically.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_current_tenant = ContextVar("current_tenant", default=None)


def get_current_tenant():
    """Return the current tenant from context (or None when unset)."""
    return _current_tenant.get()


def set_current_tenant(tenant):
    """Set current tenant and return context token for reset."""
    return _current_tenant.set(tenant)


def reset_current_tenant(token):
    """Reset tenant context using the token returned by set_current_tenant."""
    _current_tenant.reset(token)


@contextmanager
def tenant_context(tenant):
    """Context manager to execute code under a specific tenant context."""
    token = set_current_tenant(tenant)
    try:
        yield
    finally:
        reset_current_tenant(token)
