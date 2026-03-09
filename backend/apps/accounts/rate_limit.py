"""Rate limiting simples para endpoints públicos de autenticação."""

from django.conf import settings
from django.core.cache import cache

DEFAULT_AUTH_RATE_LIMITS = {
    "web_login": {"limit": 60, "window_seconds": 300},
    "web_signup": {"limit": 20, "window_seconds": 600},
    "api_token": {"limit": 60, "window_seconds": 300},
}


def _client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "").strip() or "unknown"


def _normalized_email(value: str) -> str:
    return (value or "").strip().lower()


def _get_limit_config(scope: str) -> dict:
    custom = getattr(settings, "AUTH_RATE_LIMITS", {})
    base = DEFAULT_AUTH_RATE_LIMITS[scope].copy()
    base.update(custom.get(scope, {}))
    return base


def _touch_counter(key: str, window_seconds: int) -> int:
    if cache.add(key, 1, timeout=window_seconds):
        return 1

    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        return 1


def _is_limited(scope: str, identity: str) -> bool:
    config = _get_limit_config(scope)
    window_seconds = int(config["window_seconds"])
    limit = int(config["limit"])
    key = f"rate-limit:{scope}:{identity}"
    attempts = _touch_counter(key, window_seconds=window_seconds)
    return attempts > limit


def is_web_login_limited(request) -> bool:
    email = _normalized_email(request.POST.get("email", ""))
    identity = f"{_client_ip(request)}:{email or 'unknown'}"
    return _is_limited("web_login", identity)


def is_web_signup_limited(request) -> bool:
    identity = _client_ip(request)
    return _is_limited("web_signup", identity)


def is_api_token_limited(request) -> bool:
    email = _normalized_email(request.data.get("email", "")) if hasattr(request, "data") else ""
    identity = f"{_client_ip(request)}:{email or 'unknown'}"
    return _is_limited("api_token", identity)
