"""Настройка логирования Telegram бота."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.constants import BOT_LOG_BACKUP_COUNT, BOT_LOG_MAX_BYTES


def configure_logging(log_dir: Path) -> None:
    """Создает консольный и файловый логгеры."""
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_dir / 'bot.log',
        maxBytes=BOT_LOG_MAX_BYTES,
        backupCount=BOT_LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)
