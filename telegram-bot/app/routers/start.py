"""Стартовый роутер регистрации и deep link."""

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api import BackendAPIError, BackendClient
from app.keyboards import main_keyboard, request_contact_keyboard
from app.menu import configure_private_menu_button
from app.routers.catalog import send_product_card
from app.states import RegistrationState

router = Router(name='start')


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    customer: dict,
    api: BackendClient,
    bot: Bot,
    bot_username: str,
) -> None:
    """Обрабатывает старт бота и deep link."""
    payload = command.args or ''
    settings = await api.get_settings(force=True)
    await configure_private_menu_button(
        bot,
        chat_id=message.chat.id,
        webapp_url=settings.get('catalog_webapp_url'),
    )
    if customer.get('phone'):
        await state.clear()
        await message.answer(
            'Бот готов к работе. Откройте каталог или корзину.',
            reply_markup=main_keyboard(settings.get('catalog_webapp_url')),
        )
        if payload.startswith('product_'):
            try:
                product_id = int(payload.split('_', 1)[1])
            except (IndexError, ValueError):
                return
            await send_product_card(
                bot=bot,
                api=api,
                chat_id=message.chat.id,
                product_id=product_id,
                category_id=0,
                page=1,
                bot_username=bot_username,
            )
        return
    await state.set_state(RegistrationState.waiting_contact)
    await state.update_data(start_payload=payload)
    await message.answer(
        'Для начала работы отправьте номер телефона через кнопку ниже.',
        reply_markup=request_contact_keyboard(),
    )


@router.message(F.contact)
async def save_contact(
    message: Message,
    state: FSMContext,
    customer: dict,
    api: BackendClient,
    bot: Bot,
    bot_username: str,
) -> None:
    """Сохраняет номер телефона пользователя."""
    if not message.contact or message.contact.user_id != message.from_user.id:
        await message.answer(
            'Отправьте ваш собственный контакт через кнопку запроса.'
        )
        return
    try:
        await api.sync_customer(
            {
                'telegram_id': customer['telegram_id'],
                'phone': message.contact.phone_number,
            }
        )
    except BackendAPIError as error:
        await message.answer(f'Не удалось сохранить телефон: {error}')
        return
    state_data = await state.get_data()
    await state.clear()
    settings = await api.get_settings(force=True)
    await configure_private_menu_button(
        bot,
        chat_id=message.chat.id,
        webapp_url=settings.get('catalog_webapp_url'),
    )
    await message.answer(
        'Телефон сохранен. Теперь можно оформлять заказы.',
        reply_markup=main_keyboard(settings.get('catalog_webapp_url')),
    )
    payload = state_data.get('start_payload', '')
    if payload.startswith('product_'):
        try:
            product_id = int(payload.split('_', 1)[1])
        except (IndexError, ValueError):
            return
        await send_product_card(
            bot=bot,
            api=api,
            chat_id=message.chat.id,
            product_id=product_id,
            category_id=0,
            page=1,
            bot_username=bot_username,
        )
