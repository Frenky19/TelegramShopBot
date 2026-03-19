"""Конфигурация приложения заказов."""

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Регистрирует приложение заказов."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'
    verbose_name = 'Заказы'

    def ready(self):
        """Импортирует сигналы приложения заказов."""
        from apps.orders import signals  # noqa: F401
