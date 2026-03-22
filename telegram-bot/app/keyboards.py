"""Reply и inline клавиатуры Telegram бота."""

from typing import Any

from aiogram.types import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.callbacks import (
    AdminOrderStatusCallback,
    CartActionCallback,
    CatalogNavCallback,
    OrderActionCallback,
    ProductViewCallback,
)
from app.utils import format_money

NOOP_CALLBACK_DATA = 'noop'


def main_keyboard(webapp_url: str | None) -> ReplyKeyboardMarkup:
    """Собирает главное reply-меню пользователя."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text='Каталог'), KeyboardButton(text='Корзина'))
    builder.row(KeyboardButton(text='Мои заказы'))
    builder.row(KeyboardButton(text='Помощь'))
    return builder.as_markup(resize_keyboard=True)


def request_contact_keyboard() -> ReplyKeyboardMarkup:
    """Собирает кнопку отправки собственного контакта."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text='Поделиться контактом', request_contact=True)
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def admin_chat_keyboard() -> ReplyKeyboardMarkup:
    """Собирает reply-меню для админ-группы."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text='Активные заказы'))
    return builder.as_markup(resize_keyboard=True, is_persistent=True)


def subscription_keyboard(
    channels: list[dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Собирает ссылки на обязательные подписки."""
    builder = InlineKeyboardBuilder()
    for channel in channels:
        if channel.get('subscription_url'):
            builder.row(
                InlineKeyboardButton(
                    text=f'Подписаться: {channel["title"]}',
                    url=channel['subscription_url'],
                )
            )
    builder.row(
        InlineKeyboardButton(
            text='Проверить подписку', callback_data='check_subscription'
        )
    )
    return builder.as_markup()


def catalog_keyboard(
    *,
    categories: list[dict[str, Any]],
    products: list[dict[str, Any]],
    category_id: int,
    parent_id: int | None,
    page: int,
    has_prev: bool,
    has_next: bool,
    webapp_url: str | None,
) -> InlineKeyboardMarkup:
    """Собирает inline-клавиатуру списка категорий и товаров."""
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.row(
            InlineKeyboardButton(
                text=f'📁 {category["title"]}',
                callback_data=CatalogNavCallback(
                    category_id=category['id'], page=1
                ).pack(),
            )
        )
    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f'{product["title"]} · {format_money(product["price"])}',
                callback_data=ProductViewCallback(
                    product_id=product['id'],
                    category_id=category_id,
                    page=page,
                ).pack(),
            )
        )
    pager: list[InlineKeyboardButton] = []
    if has_prev:
        pager.append(
            InlineKeyboardButton(
                text='Назад',
                callback_data=CatalogNavCallback(
                    category_id=category_id, page=page - 1
                ).pack(),
            )
        )
    if has_next:
        pager.append(
            InlineKeyboardButton(
                text='Вперед',
                callback_data=CatalogNavCallback(
                    category_id=category_id, page=page + 1
                ).pack(),
            )
        )
    if pager:
        builder.row(*pager)
    footer: list[InlineKeyboardButton] = [
        InlineKeyboardButton(
            text='Корзина',
            callback_data=CartActionCallback(action='show').pack(),
        )
    ]
    if webapp_url:
        footer.append(
            InlineKeyboardButton(
                text='Открыть WebApp',
                web_app=WebAppInfo(url=webapp_url),
            )
        )
    builder.row(*footer)
    if parent_id is not None:
        builder.row(
            InlineKeyboardButton(
                text='◀ Назад к разделу',
                callback_data=CatalogNavCallback(
                    category_id=parent_id, page=1
                ).pack(),
            )
        )
    return builder.as_markup()


def product_keyboard(
    *, product_id: int, category_id: int, page: int, share_url: str | None
) -> InlineKeyboardMarkup:
    """Собирает действия для карточки товара."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text='В корзину',
            callback_data=CartActionCallback(
                action='add', product_id=product_id
            ).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text='Корзина',
            callback_data=CartActionCallback(action='show').pack(),
        )
    )
    if share_url:
        builder.row(
            InlineKeyboardButton(
                text='Скопировать ссылку на товар',
                copy_text=CopyTextButton(text=share_url),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text='◀ Назад к каталогу',
            callback_data=CatalogNavCallback(
                category_id=category_id, page=page
            ).pack(),
        )
    )
    return builder.as_markup()


def cart_keyboard(
    items: list[dict[str, Any]], *, can_checkout: bool
) -> InlineKeyboardMarkup:
    """Собирает кнопки управления корзиной."""
    builder = InlineKeyboardBuilder()
    for item in items:
        product = item['product']
        product_id = product['id']
        quantity = item['quantity']
        builder.row(
            InlineKeyboardButton(
                text=f'➖ {product["title"]}',
                callback_data=CartActionCallback(
                    action='dec', product_id=product_id
                ).pack()
                if quantity > 1
                else NOOP_CALLBACK_DATA,
            ),
            InlineKeyboardButton(
                text=f'➕ {quantity}',
                callback_data=CartActionCallback(
                    action='inc', product_id=product_id
                ).pack(),
            ),
            InlineKeyboardButton(
                text='Удалить',
                callback_data=CartActionCallback(
                    action='remove', product_id=product_id
                ).pack(),
            ),
        )
    builder.row(
        InlineKeyboardButton(
            text='Очистить корзину',
            callback_data=CartActionCallback(action='clear').pack(),
        ),
        InlineKeyboardButton(
            text='Каталог',
            callback_data=CatalogNavCallback(category_id=0, page=1).pack(),
        ),
    )
    if can_checkout:
        builder.row(
            InlineKeyboardButton(
                text='Оформить заказ',
                callback_data=CartActionCallback(action='checkout').pack(),
            )
        )
    return builder.as_markup()


def checkout_confirm_keyboard() -> InlineKeyboardMarkup:
    """Собирает кнопки подтверждения оформления."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text='Подтвердить',
            callback_data=OrderActionCallback(
                action='confirm_checkout', order_id=0
            ).pack(),
        ),
        InlineKeyboardButton(
            text='Отмена',
            callback_data=OrderActionCallback(
                action='cancel_checkout', order_id=0
            ).pack(),
        ),
    )
    return builder.as_markup()


def payment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Собирает кнопку подтверждения оплаты."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text='Я оплатил(а)',
            callback_data=OrderActionCallback(
                action='paid', order_id=order_id
            ).pack(),
        )
    )
    return builder.as_markup()


def admin_order_keyboard(
    order_id: int, current_status: str
) -> InlineKeyboardMarkup:
    """Собирает кнопки смены статуса заказа."""
    builder = InlineKeyboardBuilder()
    for status, label in (
        ('paid', 'Оплачен'),
        ('processing', 'В обработке'),
        ('shipped', 'Отправлен'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ):
        text = f'✓ {label}' if status == current_status else label
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=AdminOrderStatusCallback(
                    order_id=order_id, status=status
                ).pack(),
            )
        )
    return builder.as_markup()
