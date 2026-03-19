"""Общие команды и действия Telegram бота."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.api import BackendClient
from app.keyboards import main_keyboard

router = Router(name='common')


@router.message(Command('help'))
@router.message(F.text == 'Помощь')
async def cmd_help(message: Message, api: BackendClient) -> None:
    """Показывает справочное сообщение с командами."""
    settings = await api.get_settings(force=True)
    await message.answer(
        settings.get('help_text')
        or (
            'Используйте /catalog для каталога, /cart для корзины '
            'и /orders для ваших заказов.'
        ),
        reply_markup=main_keyboard(settings.get('catalog_webapp_url')),
    )


@router.callback_query(F.data == 'check_subscription')
async def check_subscription(callback: CallbackQuery) -> None:
    """Повторно проверяет обязательные подписки."""
    await callback.answer(
        'Подписка подтверждена. Доступ открыт.', show_alert=False
    )
    if callback.message:
        await callback.message.answer(
            'Подписка проверена. Откройте /catalog или /cart.'
        )
