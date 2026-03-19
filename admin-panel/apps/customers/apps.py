"""Конфигурация приложения клиентов."""

from django.apps import AppConfig


class CustomersConfig(AppConfig):
    """Регистрирует приложение клиентов."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.customers'
    verbose_name = 'Клиенты'
