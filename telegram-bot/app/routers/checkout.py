"""Роутеры пошагового оформления заказа."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.api import BackendAPIError, BackendClient
from app.callbacks import CartActionCallback, OrderActionCallback
from app.constants import MAX_ADDRESS_LENGTH, MAX_FULL_NAME_LENGTH
from app.keyboards import (
    checkout_confirm_keyboard,
    payment_keyboard,
    request_contact_keyboard,
)
from app.states import CheckoutState, RegistrationState
from app.utils import format_cart, format_order

router = Router(name='checkout')


async def validate_checkout_text(
    message: Message, *, field_label: str, max_length: int
) -> str | None:
    """Проверяет текстовое поле на шаге оформления."""
    if not message.text:
        await message.answer(
            f'Отправьте {field_label.lower()} текстовым сообщением.'
        )
        return None
    value = message.text.strip()
    if not value:
        await message.answer(f'Введите {field_label.lower()}.')
        return None
    if len(value) > max_length:
        await message.answer(
            f'{field_label} не должно превышать {max_length} символов.'
        )
        return None
    return value


STALE_CART_MESSAGE = (
    'Корзина уже пуста. Заказ по этому экрану уже оформлен '
    'или товары были удалены. '
    'Откройте корзину заново и, если нужно, добавьте товары еще раз.'
)


async def clear_message_markup(callback: CallbackQuery) -> None:
    """Убирает клавиатуру у устаревшего сообщения."""
    if not callback.message:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def get_checkout_payload(state: FSMContext) -> tuple[str, str] | None:
    """Читает сохраненные данные оформления из FSM."""
    current_state = await state.get_state()
    if current_state != CheckoutState.waiting_confirmation.state:
        return None
    state_data = await state.get_data()
    full_name = state_data.get('full_name')
    address = state_data.get('address')
    if not full_name or not address:
        return None
    return full_name, address


@router.callback_query(CartActionCallback.filter(F.action == 'checkout'))
async def start_checkout(
    callback: CallbackQuery,
    state: FSMContext,
    customer: dict,
    api: BackendClient,
) -> None:
    """Запускает пошаговое оформление заказа."""
    if not customer.get('phone'):
        await state.set_state(RegistrationState.waiting_contact)
        await state.update_data(start_payload='')
        await callback.message.answer(
            'Для оформления заказа сначала отправьте номер телефона.',
            reply_markup=request_contact_keyboard(),
        )
        await callback.answer()
        return
    cart = await api.get_cart(customer['telegram_id'])
    if not cart.get('items'):
        await state.clear()
        await clear_message_markup(callback)
        await callback.answer(STALE_CART_MESSAGE, show_alert=True)
        await callback.message.answer(STALE_CART_MESSAGE)
        return
    await state.set_state(CheckoutState.waiting_full_name)
    await callback.message.answer('Введите ФИО получателя.')
    await callback.answer()


@router.message(CheckoutState.waiting_full_name)
async def checkout_full_name(message: Message, state: FSMContext) -> None:
    """Сохраняет ФИО получателя в состоянии."""
    full_name = await validate_checkout_text(
        message,
        field_label='ФИО',
        max_length=MAX_FULL_NAME_LENGTH,
    )
    if full_name is None:
        return
    normalized_full_name = ' '.join(full_name.split())
    await state.update_data(full_name=normalized_full_name)
    await state.set_state(CheckoutState.waiting_address)
    await message.answer('Введите адрес доставки.')


@router.message(CheckoutState.waiting_address)
async def checkout_address(
    message: Message, state: FSMContext, customer: dict, api: BackendClient
) -> None:
    """Сохраняет адрес доставки в состоянии."""
    address = await validate_checkout_text(
        message,
        field_label='Адрес доставки',
        max_length=MAX_ADDRESS_LENGTH,
    )
    if address is None:
        return
    await state.update_data(address=address)
    state_data = await state.get_data()
    cart = await api.get_cart(customer['telegram_id'])
    if not cart.get('items'):
        await state.clear()
        await message.answer(STALE_CART_MESSAGE)
        return
    text = '\n\n'.join(
        [
            format_cart(cart),
            (
                f'ФИО: <b>{state_data["full_name"]}</b>\n'
                f'Адрес: <b>{address}</b>\n'
                f'Телефон: <b>{customer["phone"]}</b>'
            ),
        ]
    )
    await state.set_state(CheckoutState.waiting_confirmation)
    await message.answer(text, reply_markup=checkout_confirm_keyboard())


@router.callback_query(
    OrderActionCallback.filter(F.action == 'cancel_checkout')
)
async def cancel_checkout(callback: CallbackQuery, state: FSMContext) -> None:
    """Останавливает оформление заказа."""
    checkout_payload = await get_checkout_payload(state)
    if checkout_payload is None:
        text = (
            'Заказ уже создан. Отменить оплаченный заказ '
            'через бота нельзя. '
            'Если действительно хотите отменить заказ, '
            'напишите в службу поддержки.'
        )
        await clear_message_markup(callback)
        await callback.answer(text, show_alert=True)
        await callback.message.answer(text)
        return
    await state.clear()
    await clear_message_markup(callback)
    await callback.answer('Оформление заказа отменено.')
    await callback.message.answer('Оформление заказа отменено.')


@router.callback_query(
    OrderActionCallback.filter(F.action == 'confirm_checkout')
)
async def confirm_checkout(
    callback: CallbackQuery,
    state: FSMContext,
    customer: dict,
    api: BackendClient,
) -> None:
    """Создает заказ после подтверждения данных."""
    checkout_payload = await get_checkout_payload(state)
    if checkout_payload is None:
        await clear_message_markup(callback)
        await callback.answer(
            (
                'Этот экран оформления уже неактуален. Если нужно, '
                'откройте корзину и начните оформление заново.'
            ),
            show_alert=True,
        )
        return
    full_name, address = checkout_payload
    try:
        order = await api.checkout(
            telegram_id=customer['telegram_id'],
            full_name=full_name,
            address=address,
        )
    except BackendAPIError as error:
        if str(error).strip() == 'Корзина пуста.':
            await state.clear()
            await clear_message_markup(callback)
            await callback.answer(STALE_CART_MESSAGE, show_alert=True)
            await callback.message.answer(STALE_CART_MESSAGE)
            return
        await callback.answer(str(error), show_alert=True)
        return
    await state.clear()
    await clear_message_markup(callback)
    await callback.answer('Заказ создан.')
    await callback.message.answer(
        '\n\n'.join(
            [
                format_order(order),
                f'Платежная заглушка: <code>{order["payment_stub_id"]}</code>',
            ]
        ),
        reply_markup=payment_keyboard(order['id']),
    )


@router.callback_query(OrderActionCallback.filter(F.action == 'paid'))
async def mark_order_paid(
    callback: CallbackQuery,
    callback_data: OrderActionCallback,
    api: BackendClient,
) -> None:
    """Принимает отметку пользователя об оплате."""
    try:
        order = await api.mark_paid(callback_data.order_id)
    except BackendAPIError as error:
        await callback.answer(str(error), show_alert=True)
        return
    await clear_message_markup(callback)
    await callback.answer('Статус оплаты отправлен администратору.')
    await callback.message.answer(
        f'Заказ #{order["id"]} переведен в статус: '
        f'<b>{order["status_display"]}</b>.'
    )
