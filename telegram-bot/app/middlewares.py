"""Middleware для регистрации, подписок и логирования."""

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    TelegramObject,
    Update,
)

from app.api import BackendAPIError, BackendClient
from app.keyboards import subscription_keyboard
from app.utils import resolve_update_meta

logger = logging.getLogger('telegram_shop.bot')


class UpdateLoggingMiddleware(BaseMiddleware):
    """Логирует метаданные каждого апдейта."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        """Пишет лог до и после обработки апдейта."""
        actual_event, user, chat_id, event_type = resolve_update_meta(event)
        telegram_id = getattr(user, 'id', None)
        username = getattr(user, 'username', None)
        started_at = time.perf_counter()
        data['event_type'] = event_type
        data['actual_event'] = actual_event
        try:
            result = await handler(event, data)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.exception(
                (
                    'update_failed telegram_id=%s username=%s chat_id=%s '
                    'update_type=%s duration_ms=%.2f'
                ),
                telegram_id,
                username,
                chat_id,
                event_type,
                duration_ms,
            )
            raise
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            (
                'update_processed telegram_id=%s username=%s chat_id=%s '
                'update_type=%s duration_ms=%.2f'
            ),
            telegram_id,
            username,
            chat_id,
            event_type,
            duration_ms,
        )
        return result


class RegistrationMiddleware(BaseMiddleware):
    """Не пускает незарегистрированных пользователей дальше."""

    def __init__(self, api: BackendClient) -> None:
        """Сохраняет клиент backend для проверки профиля."""
        self.api = api

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        """Блокирует незарегистрированных пользователей."""
        _, user, _, _ = resolve_update_meta(event)
        if not user:
            return await handler(event, data)
        try:
            customer = await self.api.sync_customer(
                {
                    'telegram_id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'language_code': user.language_code or '',
                }
            )
        except BackendAPIError as error:
            logger.exception('Failed to sync customer: %s', error)
            return await self._reject(
                resolve_update_meta(event)[0], 'Backend временно недоступен.'
            )
        data['customer'] = customer
        return await handler(event, data)

    async def _reject(self, event: TelegramObject, text: str) -> None:
        """Просит пользователя отправить свой контакт."""
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, InlineQuery):
            await event.answer(
                [
                    InlineQueryResultArticle(
                        id='backend-error',
                        title='Сервис временно недоступен',
                        input_message_content=InputTextMessageContent(
                            message_text=text
                        ),
                        description='Попробуйте чуть позже.',
                    )
                ],
                cache_time=0,
                is_personal=True,
            )
        return None


class SubscriptionMiddleware(BaseMiddleware):
    """Требует подписку на обязательные каналы."""

    def __init__(self, api: BackendClient) -> None:
        """Сохраняет клиент backend для проверки подписок."""
        self.api = api

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        """Останавливает сценарий без обязательной подписки."""
        bot = data['bot']
        actual_event, user, chat_id, _ = resolve_update_meta(event)
        if not user:
            return await handler(event, data)
        try:
            settings = await self.api.get_settings()
        except BackendAPIError as error:
            logger.exception('Failed to fetch bot settings: %s', error)
            return await self._deny(
                actual_event, 'Не удалось получить настройки бота.', []
            )
        if (
            chat_id
            and settings.get('admin_chat_id')
            and chat_id == settings['admin_chat_id']
        ):
            return await handler(event, data)
        required_channels = settings.get('required_channels') or []
        if not required_channels:
            return await handler(event, data)
        missing_channels: list[dict[str, Any]] = []
        for channel in required_channels:
            identifier = channel.get('chat_id') or channel.get('username')
            if not identifier:
                continue
            try:
                member = await bot.get_chat_member(identifier, user.id)
            except Exception:
                missing_channels.append(channel)
                continue
            if member.status not in {
                'member',
                'administrator',
                'creator',
                'restricted',
            }:
                missing_channels.append(channel)
        if missing_channels:
            return await self._deny(
                actual_event,
                settings.get('subscription_message')
                or (
                    'Для продолжения требуется подписка '
                    'на обязательные каналы.'
                ),
                missing_channels,
            )
        return await handler(event, data)

    async def _deny(
        self, event: TelegramObject, text: str, channels: list[dict[str, Any]]
    ) -> None:
        """Показывает сообщение и кнопки подписки."""
        reply_markup = subscription_keyboard(channels)
        if isinstance(event, Message):
            await event.answer(text, reply_markup=reply_markup)
        elif isinstance(event, CallbackQuery):
            await event.answer(
                'Сначала подпишитесь на обязательные каналы.', show_alert=True
            )
            if event.message:
                await event.message.answer(text, reply_markup=reply_markup)
        elif isinstance(event, InlineQuery):
            await event.answer(
                [
                    InlineQueryResultArticle(
                        id='subscribe-required',
                        title='Нужна подписка',
                        input_message_content=InputTextMessageContent(
                            message_text=text
                        ),
                        description=(
                            'Подпишитесь на каналы и повторите запрос.'
                        ),
                    )
                ],
                cache_time=0,
                is_personal=True,
            )
        return None
