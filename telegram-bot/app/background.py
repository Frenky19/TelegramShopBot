"""Фоновые воркеры уведомлений и рассылок."""

import asyncio
import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.api import BackendAPIError, BackendClient
from app.constants import BROADCAST_SEND_DELAY_SECONDS
from app.keyboards import admin_chat_keyboard, admin_order_keyboard
from app.utils import format_order

logger = logging.getLogger('telegram_shop.bot')
ADMIN_KEYBOARD_SHOWN_CHATS: set[int] = set()


async def notification_worker(
    bot: Bot, api: BackendClient, interval: int
) -> None:
    """Опрашивает очередь уведомлений и отправляет сообщения."""
    logger.info('Notification worker started. poll_interval=%s', interval)
    while True:
        try:
            notifications = await api.claim_notifications()
            if notifications:
                logger.info(
                    'Claimed %s notification(s) for delivery.',
                    len(notifications),
                )
            for notification in notifications:
                try:
                    await handle_notification(bot, api, notification)
                    await api.complete_notification(notification['id'])
                except Exception as error:
                    logger.exception(
                        'Failed to process notification %s', notification['id']
                    )
                    await api.fail_notification(notification['id'], str(error))
        except BackendAPIError as error:
            logger.warning('Notification polling failed: %s', error)
        except Exception:
            logger.exception(
                'Notification worker crashed during polling cycle.'
            )
        await asyncio.sleep(interval)


async def handle_notification(
    bot: Bot, api: BackendClient, notification: dict
) -> None:
    """Отправляет одно уведомление по заказу."""
    event_type = notification['event_type']
    order = notification.get('order')
    if event_type == 'new_order':
        settings = await api.get_settings(force=True)
        admin_chat_id = settings.get('admin_chat_id')
        if not admin_chat_id:
            raise RuntimeError('Admin chat id is not configured.')
        if admin_chat_id not in ADMIN_KEYBOARD_SHOWN_CHATS:
            await bot.send_message(
                admin_chat_id,
                (
                    'Панель администратора подключена. Кнопка '
                    "'Активные заказы' теперь доступна внизу чата."
                ),
                reply_markup=admin_chat_keyboard(),
            )
            ADMIN_KEYBOARD_SHOWN_CHATS.add(admin_chat_id)
        await bot.send_message(
            admin_chat_id,
            format_order(order, admin=True),
            reply_markup=admin_order_keyboard(order['id'], order['status']),
        )
        return
    if event_type == 'order_status_updated':
        customer = notification.get('customer') or order.get('customer')
        if not customer:
            raise RuntimeError('Notification customer is missing.')
        await bot.send_message(
            customer['telegram_id'],
            f'Статус заказа #{order["id"]} изменен: {order["status_display"]}',
        )


async def broadcast_worker(
    bot: Bot, api: BackendClient, interval: int
) -> None:
    """Опрашивает очередь рассылок и запускает отправку."""
    logger.info('Broadcast worker started. poll_interval=%s', interval)
    while True:
        try:
            broadcast = await api.claim_broadcast()
            if broadcast and broadcast.get('id'):
                await handle_broadcast(bot, api, broadcast)
        except BackendAPIError as error:
            logger.warning('Broadcast polling failed: %s', error)
        except Exception:
            logger.exception('Broadcast worker crashed during polling cycle.')
        await asyncio.sleep(interval)


async def handle_broadcast(
    bot: Bot, api: BackendClient, broadcast: dict
) -> None:
    """Рассылает одно маркетинговое сообщение получателям."""
    delivered_count = 0
    error_count = 0
    last_error = ''
    media_content: bytes | None = None
    if broadcast.get('image'):
        media_content = await api.download_media(broadcast['image'])
    for telegram_id in broadcast.get('recipients', []):
        try:
            if media_content:
                await bot.send_photo(
                    telegram_id,
                    BufferedInputFile(
                        media_content,
                        filename=f'broadcast-{broadcast["id"]}.jpg',
                    ),
                    caption=broadcast['text'],
                )
            else:
                await bot.send_message(telegram_id, broadcast['text'])
            delivered_count += 1
        except Exception as error:
            error_count += 1
            last_error = str(error)
        await asyncio.sleep(BROADCAST_SEND_DELAY_SECONDS)
    await api.report_broadcast(
        broadcast['id'],
        delivered_count=delivered_count,
        error_count=error_count,
        last_error=last_error,
    )
