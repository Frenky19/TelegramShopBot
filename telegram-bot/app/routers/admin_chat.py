"""Роутеры админ группы для управления заказами."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.api import BackendAPIError, BackendClient
from app.callbacks import AdminOrderStatusCallback
from app.filters import IsAdmin
from app.keyboards import (
    admin_chat_keyboard,
    admin_order_keyboard,
    main_keyboard,
)
from app.utils import format_order

router = Router(name='admin_chat')


async def send_active_orders(message: Message, api: BackendClient) -> bool:
    """Отправляет администратору список активных заказов."""
    settings = await api.get_settings(force=True)
    if message.chat.id != settings.get('admin_chat_id'):
        await message.answer(
            'Команда доступна только в админ-чате.',
            reply_markup=main_keyboard(settings.get('catalog_webapp_url')),
        )
        return False
    orders = await api.get_active_orders()
    if not orders:
        await message.answer(
            'Активных заказов нет.', reply_markup=admin_chat_keyboard()
        )
        return True
    await message.answer(
        'Панель администратора обновлена.', reply_markup=admin_chat_keyboard()
    )
    for order in orders:
        await message.answer(
            format_order(order, admin=True),
            reply_markup=admin_order_keyboard(order['id'], order['status']),
        )
    return True


@router.message(Command('active_orders'), IsAdmin())
async def active_orders(message: Message, api: BackendClient) -> None:
    """Показывает активные заказы по команде."""
    await send_active_orders(message, api)


@router.message(F.text == 'Активные заказы', IsAdmin())
async def active_orders_text_button(
    message: Message, api: BackendClient
) -> None:
    """Показывает активные заказы по reply-кнопке."""
    await send_active_orders(message, api)


@router.message(Command('active_orders'))
async def active_orders_denied(message: Message) -> None:
    """Сообщает, что команда доступна только администраторам."""
    await message.answer(
        (
            'Недостаточно прав. В админке откройте раздел "Клиенты" '
            "и включите флаг 'Админ бота'."
        )
    )


@router.callback_query(AdminOrderStatusCallback.filter(), IsAdmin())
async def update_order_status(
    callback: CallbackQuery,
    callback_data: AdminOrderStatusCallback,
    api: BackendClient,
) -> None:
    """Сохраняет новый статус заказа."""
    settings = await api.get_settings(force=True)
    if callback.message.chat.id != settings.get('admin_chat_id'):
        await callback.answer(
            'Действие доступно только в админ-чате.', show_alert=True
        )
        return
    try:
        order = await api.set_order_status(
            callback_data.order_id, callback_data.status
        )
    except BackendAPIError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.message.edit_text(
        format_order(order, admin=True),
        reply_markup=admin_order_keyboard(order['id'], order['status']),
    )
    await callback.answer('Статус обновлен.')


@router.callback_query(AdminOrderStatusCallback.filter())
async def update_order_status_denied(callback: CallbackQuery) -> None:
    """Сообщает об отсутствии прав на смену статуса."""
    await callback.answer(
        (
            'Нет прав на управление заказами. Включите для этого '
            "пользователя флаг 'Админ бота' в админке."
        ),
        show_alert=True,
    )
