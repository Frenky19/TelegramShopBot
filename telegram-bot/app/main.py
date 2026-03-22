"""Точка входа и регистрация роутеров Telegram бота."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    MenuButtonDefault,
    MenuButtonWebApp,
    WebAppInfo,
)

from app.api import BackendAPIError, BackendClient
from app.background import broadcast_worker, notification_worker
from app.config import Settings
from app.logging import configure_logging
from app.middlewares import (
    RegistrationMiddleware,
    SubscriptionMiddleware,
    UpdateLoggingMiddleware,
)
from app.routers.admin_chat import router as admin_router
from app.routers.cart import router as cart_router
from app.routers.catalog import router as catalog_router
from app.routers.checkout import router as checkout_router
from app.routers.common import router as common_router
from app.routers.faq import router as faq_router
from app.routers.orders import router as orders_router
from app.routers.start import router as start_router


async def register_commands(bot: Bot, api: BackendClient) -> None:
    """Настраивает список команд в Telegram."""
    public_commands = [
        BotCommand(command='start', description='Запуск бота'),
        BotCommand(command='catalog', description='Открыть каталог'),
        BotCommand(command='cart', description='Открыть корзину'),
        BotCommand(command='orders', description='Мои заказы'),
        BotCommand(command='help', description='Помощь'),
    ]
    await bot.delete_my_commands()
    await bot.set_my_commands(
        public_commands, scope=BotCommandScopeAllPrivateChats()
    )
    try:
        settings = await api.get_settings(force=True)
    except BackendAPIError:
        return
    webapp_url = settings.get('catalog_webapp_url')
    if webapp_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text='Открыть WebApp',
                web_app=WebAppInfo(url=webapp_url),
            )
        )
    else:
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
    admin_chat_id = settings.get('admin_chat_id')
    if not admin_chat_id:
        return
    await bot.set_my_commands(
        [BotCommand(command='active_orders', description='Активные заказы')],
        scope=BotCommandScopeChat(chat_id=admin_chat_id),
    )


async def main() -> None:
    """Запускает основной сценарий приложения."""
    settings = Settings()
    configure_logging(settings.logs_path)

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    api = BackendClient(
        backend_url=settings.backend_url,
        media_base_url=settings.media_base_url,
        service_token=settings.service_token,
        settings_cache_ttl=settings.settings_cache_ttl,
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_routers(
        start_router,
        common_router,
        orders_router,
        catalog_router,
        cart_router,
        checkout_router,
        admin_router,
        faq_router,
    )
    dispatcher.update.outer_middleware(UpdateLoggingMiddleware())
    dispatcher.update.outer_middleware(RegistrationMiddleware(api))
    dispatcher.update.outer_middleware(SubscriptionMiddleware(api))
    me = await bot.get_me()
    await register_commands(bot, api)
    notification_task = asyncio.create_task(
        notification_worker(bot, api, settings.notification_poll_interval)
    )
    broadcast_task = asyncio.create_task(
        broadcast_worker(bot, api, settings.broadcast_poll_interval)
    )
    try:
        await dispatcher.start_polling(
            bot,
            api=api,
            settings=settings,
            bot_username=me.username or '',
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        notification_task.cancel()
        broadcast_task.cancel()
        await asyncio.gather(
            notification_task, broadcast_task, return_exceptions=True
        )
        await api.close()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
