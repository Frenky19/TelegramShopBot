"""Конфигурация приложения настроек бота."""

from django.apps import AppConfig


class BotconfigConfig(AppConfig):
    """Регистрирует приложение настроек бота."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.botconfig'
    verbose_name = 'Настройки бота'
