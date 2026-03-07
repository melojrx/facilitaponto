"""
Settings de produção (EasyPanel + VPS).
Ativo quando DJANGO_SETTINGS_MODULE=config.settings.production
"""
from .base import *  # noqa: F401, F403

DEBUG = False

# Segurança em produção
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
