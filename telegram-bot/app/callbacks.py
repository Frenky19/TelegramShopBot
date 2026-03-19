"""Схемы callback данных inline кнопок бота."""

from aiogram.filters.callback_data import CallbackData


class CatalogNavCallback(CallbackData, prefix='cat'):
    """Хранит данные навигации по каталогу."""

    category_id: int
    page: int = 1


class ProductViewCallback(CallbackData, prefix='prd'):
    """Хранит данные для открытия товара."""

    product_id: int
    category_id: int = 0
    page: int = 1


class CartActionCallback(CallbackData, prefix='cart'):
    """Хранит действие пользователя в корзине."""

    action: str
    product_id: int = 0


class OrderActionCallback(CallbackData, prefix='ord'):
    """Хранит действие пользователя с заказом."""

    action: str
    order_id: int


class AdminOrderStatusCallback(CallbackData, prefix='adm'):
    """Хранит новый статус заказа для админа."""

    order_id: int
    status: str
