"""Конфигурация приложения каталога."""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Регистрирует приложение каталога."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.catalog'
    verbose_name = 'Каталог'
