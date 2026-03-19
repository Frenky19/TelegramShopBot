"""Роутеры корзины Telegram бота."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.api import BackendAPIError, BackendClient
from app.callbacks import CartActionCallback
from app.keyboards import cart_keyboard
from app.utils import format_cart

router = Router(name='cart')


async def render_cart(
    message: Message,
    api: BackendClient,
    telegram_id: int,
) -> None:
    """Формирует и отправляет актуальную корзину."""
    cart = await api.get_cart(telegram_id)
    await message.answer(
        format_cart(cart),
        reply_markup=cart_keyboard(
            cart.get('items', []),
            can_checkout=bool(cart.get('items')),
        ),
    )


def find_cart_item(cart: dict, product_id: int) -> dict | None:
    """Находит товар в сериализованной корзине."""
    for item in cart.get('items', []):
        product = item.get('product') or {}
        if product.get('id') == product_id:
            return item
    return None


@router.message(Command('cart'))
@router.message(F.text == 'Корзина')
async def cmd_cart(
    message: Message,
    customer: dict,
    api: BackendClient,
) -> None:
    """Открывает корзину по команде или кнопке."""
    await render_cart(message, api, customer['telegram_id'])


@router.callback_query(F.data == 'noop')
async def noop_callback(callback: CallbackQuery) -> None:
    """Игнорирует технические нажатия без действия."""
    await callback.answer()


@router.callback_query(
    CartActionCallback.filter(
        F.action.in_(('show', 'add', 'inc', 'dec', 'remove', 'clear'))
    )
)
async def cart_actions(
    callback: CallbackQuery,
    callback_data: CartActionCallback,
    customer: dict,
    api: BackendClient,
) -> None:
    """Обрабатывает изменение корзины из inline-кнопок."""
    action = callback_data.action
    telegram_id = customer['telegram_id']
    try:
        if action == 'show':
            cart = await api.get_cart(telegram_id)
        elif action == 'add':
            cart = await api.update_cart_item(
                telegram_id=telegram_id,
                product_id=callback_data.product_id,
                mode='increment',
                delta=1,
            )
            await callback.answer('Товар добавлен в корзину.')
            return
        elif action == 'inc':
            cart = await api.update_cart_item(
                telegram_id=telegram_id,
                product_id=callback_data.product_id,
                mode='increment',
                delta=1,
            )
        elif action == 'dec':
            current_cart = await api.get_cart(telegram_id)
            cart_item = find_cart_item(current_cart, callback_data.product_id)
            if not cart_item or cart_item['quantity'] <= 1:
                await callback.message.edit_text(
                    format_cart(current_cart),
                    reply_markup=cart_keyboard(
                        current_cart.get('items', []),
                        can_checkout=bool(current_cart.get('items')),
                    ),
                )
                await callback.answer('Минимальное количество — 1.')
                return
            cart = await api.update_cart_item(
                telegram_id=telegram_id,
                product_id=callback_data.product_id,
                mode='increment',
                delta=-1,
            )
        elif action == 'remove':
            cart = await api.update_cart_item(
                telegram_id=telegram_id,
                product_id=callback_data.product_id,
                mode='set',
                quantity=0,
            )
        elif action == 'clear':
            cart = await api.clear_cart(telegram_id)
        else:
            return
    except BackendAPIError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await callback.message.edit_text(
        format_cart(cart),
        reply_markup=cart_keyboard(
            cart.get('items', []),
            can_checkout=bool(cart.get('items')),
        ),
    )
    await callback.answer()
