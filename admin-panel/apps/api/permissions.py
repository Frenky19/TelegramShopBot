"""Права доступа для внутреннего сервисного API."""

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasServiceToken(BasePermission):
    """Проверяет сервисный токен внутренних запросов."""

    message = 'Invalid service token.'

    def has_permission(self, request, view):
        """Проверяет заголовок сервисного токена."""
        return (
            request.headers.get('X-Service-Token')
            == settings.INTERNAL_SERVICE_TOKEN
        )
