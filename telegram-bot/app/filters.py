"""Фильтры доступа для обработчиков бота."""

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class IsAdmin(BaseFilter):
    """Пропускает только администраторов бота."""

    async def __call__(
        self, event: TelegramObject, customer: dict | None = None
    ) -> bool:
        """Проверяет флаг администратора у клиента."""
        return bool(customer and customer.get('is_bot_admin'))
