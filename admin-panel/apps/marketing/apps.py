"""Конфигурация приложения маркетинга."""

from django.apps import AppConfig


class MarketingConfig(AppConfig):
    """Регистрирует маркетинговое приложение."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketing'
    verbose_name = 'Маркетинг'
