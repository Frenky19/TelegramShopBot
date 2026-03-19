"""Роутеры каталога и карточек товаров."""

from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaPhoto,
    Message,
)

from app.api import BackendAPIError, BackendClient
from app.callbacks import CatalogNavCallback, ProductViewCallback
from app.constants import TELEGRAM_MEDIA_GROUP_LIMIT
from app.keyboards import catalog_keyboard, product_keyboard
from app.utils import format_product

router = Router(name='catalog')


def find_category(
    categories: list[dict[str, Any]],
    category_id: int,
) -> tuple[dict[str, Any] | None, int | None]:
    """Ищет категорию по идентификатору в дереве."""
    for category in categories:
        if category['id'] == category_id:
            return category, category.get('parent')
        found, parent_id = find_category(
            category.get('children', []),
            category_id,
        )
        if found:
            return found, parent_id
    return None, None


async def build_catalog_view(
    api: BackendClient,
    category_id: int,
    page: int,
) -> tuple[str, Any]:
    """Готовит категории, товары и пагинацию каталога."""
    categories = await api.get_categories()
    current_category = None
    parent_id = None
    child_categories = categories
    title = 'Каталог'
    if category_id:
        current_category, parent_id = find_category(categories, category_id)
        if current_category:
            title = current_category['title']
            child_categories = current_category.get('children', [])
            parent_id = (
                current_category.get('parent')
                if current_category.get('parent') is not None
                else 0
            )
    products = await api.get_products(
        category_id=category_id or None,
        page=page,
    )
    settings = await api.get_settings()
    text = f'<b>{title}</b>\n\nВыберите раздел или товар.'
    if not child_categories and not products.get('results'):
        text = f'<b>{title}</b>\n\nВ этом разделе пока нет товаров.'
    keyboard = catalog_keyboard(
        categories=child_categories,
        products=products.get('results', []),
        category_id=category_id,
        parent_id=parent_id if category_id else None,
        page=page,
        has_prev=bool(products.get('previous')),
        has_next=bool(products.get('next')),
        webapp_url=settings.get('catalog_webapp_url'),
    )
    return text, keyboard


async def render_catalog_message(
    message: Message,
    api: BackendClient,
    category_id: int = 0,
    page: int = 1,
) -> None:
    """Отправляет пользователю текущий экран каталога."""
    text, keyboard = await build_catalog_view(api, category_id, page)
    await message.answer(text, reply_markup=keyboard)


async def send_product_card(
    *,
    bot: Bot,
    api: BackendClient,
    chat_id: int,
    product_id: int,
    category_id: int,
    page: int,
    bot_username: str,
) -> None:
    """Показывает карточку товара с фото и действиями."""
    product = await api.get_product(product_id)
    media_items = []
    for image in product.get('images', [])[:TELEGRAM_MEDIA_GROUP_LIMIT]:
        if not image.get('image'):
            continue
        try:
            content = await api.download_media(image['image'])
        except Exception:
            continue
        media_items.append(
            InputMediaPhoto(
                media=BufferedInputFile(
                    content,
                    filename=f'product-{product_id}-{image["id"]}.jpg',
                ),
            )
        )
    if media_items:
        await bot.send_media_group(chat_id, media_items)
    share_url = (
        f'https://t.me/{bot_username}?start=product_{product_id}'
        if bot_username
        else None
    )
    await bot.send_message(
        chat_id,
        format_product(product),
        reply_markup=product_keyboard(
            product_id=product_id,
            category_id=category_id,
            page=page,
            share_url=share_url,
        ),
    )


@router.message(Command('catalog'))
@router.message(F.text == 'Каталог')
async def cmd_catalog(message: Message, api: BackendClient) -> None:
    """Открывает корень каталога."""
    await render_catalog_message(message, api, category_id=0, page=1)


@router.callback_query(CatalogNavCallback.filter())
async def navigate_catalog(
    callback: CallbackQuery,
    callback_data: CatalogNavCallback,
    api: BackendClient,
) -> None:
    """Переключает пользователя между разделами каталога."""
    text, keyboard = await build_catalog_view(
        api,
        callback_data.category_id,
        callback_data.page,
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(ProductViewCallback.filter())
async def open_product(
    callback: CallbackQuery,
    callback_data: ProductViewCallback,
    api: BackendClient,
    bot: Bot,
    bot_username: str,
) -> None:
    """Открывает товар по callback-кнопке."""
    try:
        await send_product_card(
            bot=bot,
            api=api,
            chat_id=callback.message.chat.id,
            product_id=callback_data.product_id,
            category_id=callback_data.category_id,
            page=callback_data.page,
            bot_username=bot_username,
        )
        await callback.answer()
    except BackendAPIError as error:
        await callback.answer(str(error), show_alert=True)
