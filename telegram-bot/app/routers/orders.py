"""Роутер просмотра заказов клиента."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api import BackendAPIError, BackendClient
from app.keyboards import main_keyboard
from app.utils import format_order, is_private_message

router = Router(name='orders')


@router.message(Command('orders'))
@router.message(F.text == 'Мои заказы')
async def my_orders(
    message: Message, customer: dict, api: BackendClient
) -> None:
    """Показывает клиенту его активные заказы."""
    settings = await api.get_settings(force=True)
    reply_markup = main_keyboard(settings.get('catalog_webapp_url'))
    if not is_private_message(message):
        await message.answer('Команда доступна только в личном чате с ботом.')
        return
    try:
        orders = await api.get_customer_active_orders(customer['telegram_id'])
    except BackendAPIError as error:
        await message.answer(
            f'Не удалось получить список заказов: {error}',
            reply_markup=reply_markup,
        )
        return
    if not orders:
        await message.answer(
            'У вас нет активных заказов.', reply_markup=reply_markup
        )
        return
    await message.answer('Ваши активные заказы:', reply_markup=reply_markup)
    for order in orders:
        await message.answer(format_order(order))
