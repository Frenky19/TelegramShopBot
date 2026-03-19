"""Вспомогательные функции форматирования и разбора апдейтов."""

import html
from typing import Any

from aiogram.types import CallbackQuery, Message, Update, User

from app.constants import TEXT_TRUNCATE_LIMIT


def format_money(value: Any) -> str:
    """Преобразует сумму в строку для интерфейса."""
    return f'{float(value):.2f} ₽'


def escape(value: str | None) -> str:
    """Экранирует текст для HTML-разметки."""
    return html.escape(value or '')


def truncate(
    value: str | None,
    limit: int = TEXT_TRUNCATE_LIMIT,
) -> str:
    """Сокращает текст до заданной длины."""
    value = (value or '').strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + '…'


def format_product(product: dict[str, Any]) -> str:
    """Собирает текст карточки товара."""
    lines = [
        f'<b>{escape(product["title"])}</b>',
        f'Цена: <b>{format_money(product["price"])}</b>',
    ]
    if product.get('description'):
        lines.append('')
        lines.append(escape(product['description']))
    return '\n'.join(lines)


def format_cart(cart: dict[str, Any]) -> str:
    """Собирает текст корзины пользователя."""
    items = cart.get('items') or []
    if not items:
        return 'Корзина пуста.'
    lines = ['<b>Корзина</b>', '']
    for index, item in enumerate(items, start=1):
        product = item['product']
        lines.append(
            f'{index}. {escape(product["title"])} x '
            f'{item["quantity"]} = '
            f'<b>{format_money(item["line_total"])}</b>'
        )
    lines.append('')
    lines.append(f'Итого: <b>{format_money(cart["total_amount"])}</b>')
    return '\n'.join(lines)


def format_order(order: dict[str, Any], *, admin: bool = False) -> str:
    """Собирает текст карточки заказа."""
    lines = [
        f'<b>Заказ #{order["id"]}</b>',
        f'Статус: <b>{escape(order["status_display"])}</b>',
        f'Клиент: {escape(order["full_name"])}',
        f'Телефон: {escape(order["phone"])}',
        f'Адрес: {escape(order["address"])}',
        '',
        '<b>Позиции</b>',
    ]
    for item in order.get('items', []):
        lines.append(
            f'• {escape(item["product_title"])} x '
            f'{item["quantity"]} = '
            f'<b>{format_money(item["line_total"])}</b>'
        )
    lines.append('')
    lines.append(f'Итого: <b>{format_money(order["total_amount"])}</b>')
    if admin and order.get('customer'):
        customer = order['customer']
        lines.append(
            f'Telegram ID: '
            f'<code>{customer["telegram_id"]}</code>'
        )
    return '\n'.join(lines)


def resolve_update_meta(
    update: Update,
) -> tuple[Any, User | None, int | None, str]:
    """Извлекает chat_id, telegram_id и тип апдейта."""
    event = update.event
    event_type = update.event_type
    user = getattr(event, 'from_user', None)
    chat_id = getattr(getattr(event, 'chat', None), 'id', None)
    if chat_id is None and isinstance(event, CallbackQuery) and event.message:
        chat_id = event.message.chat.id
    return event, user, chat_id, event_type


def is_private_message(message: Message | None) -> bool:
    """Проверяет, что апдейт пришел из личного чата."""
    return bool(message and message.chat and message.chat.type == 'private')
