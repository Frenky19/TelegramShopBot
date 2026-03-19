"""Конфигурация приложения базовых компонентов."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Регистрирует базовое приложение проекта."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'
