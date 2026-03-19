"""Настройки запуска Telegram бота."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    DEFAULT_BROADCAST_POLL_INTERVAL_SECONDS,
    DEFAULT_NOTIFICATION_POLL_INTERVAL_SECONDS,
    DEFAULT_SETTINGS_CACHE_TTL_SECONDS,
)


class Settings(BaseSettings):
    """Хранит параметры запуска бота и интеграций."""

    bot_token: str = Field(alias='TELEGRAM_BOT_TOKEN')
    backend_url: str = Field(
        default='http://admin-panel:8000', alias='BACKEND_URL'
    )
    media_base_url: str = Field(
        default='http://admin-panel:8000', alias='MEDIA_BASE_URL'
    )
    service_token: str = Field(
        default='dev-service-token', alias='INTERNAL_SERVICE_TOKEN'
    )
    settings_cache_ttl: int = Field(
        default=DEFAULT_SETTINGS_CACHE_TTL_SECONDS,
        alias='SETTINGS_CACHE_TTL',
    )
    notification_poll_interval: int = Field(
        default=DEFAULT_NOTIFICATION_POLL_INTERVAL_SECONDS,
        alias='NOTIFICATION_POLL_INTERVAL',
    )
    broadcast_poll_interval: int = Field(
        default=DEFAULT_BROADCAST_POLL_INTERVAL_SECONDS,
        alias='BROADCAST_POLL_INTERVAL',
    )
    logs_dir: str = Field(default='logs', alias='LOGS_DIR')

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    @property
    def logs_path(self) -> Path:
        """Возвращает путь к директории логов бота."""
        return Path(self.logs_dir)
