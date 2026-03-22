"""Настройка системной кнопки меню Telegram для приватных чатов."""

from aiogram import Bot
from aiogram.types import MenuButtonDefault, MenuButtonWebApp, WebAppInfo


async def configure_private_menu_button(
    bot: Bot,
    *,
    webapp_url: str | None,
    chat_id: int | None = None,
) -> None:
    """Переключает системную кнопку меню на запуск WebApp."""
    if webapp_url:
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonWebApp(
                text='Открыть WebApp',
                web_app=WebAppInfo(url=webapp_url),
            ),
        )
        return

    await bot.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonDefault(),
    )
