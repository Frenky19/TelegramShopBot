"""Аутентификация Telegram WebApp и синхронизация клиентов."""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from django.conf import settings
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from apps.customers.models import Customer


@dataclass
class TelegramAuthPayload:
    """Хранит клиента и сырой payload из Telegram."""

    customer: Customer
    data: dict


def validate_init_data(init_data: str) -> dict:
    """Проверяет подпись и срок жизни initData."""
    if not init_data:
        raise exceptions.AuthenticationFailed('Missing initData header.')
    if not settings.TELEGRAM_BOT_TOKEN:
        raise exceptions.AuthenticationFailed(
            'Telegram bot token is not configured.'
        )
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    provided_hash = pairs.pop('hash', None)
    if not provided_hash:
        raise exceptions.AuthenticationFailed('initData hash is missing.')
    data_check_string = '\n'.join(
        f'{key}={value}' for key, value in sorted(pairs.items())
    )
    secret_key = hmac.new(
        b'WebAppData',
        settings.TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, provided_hash):
        raise exceptions.AuthenticationFailed('Invalid initData signature.')
    try:
        auth_date = int(pairs.get('auth_date', '0'))
    except (TypeError, ValueError) as error:
        raise exceptions.AuthenticationFailed(
            'Invalid initData auth_date.'
        ) from error
    if auth_date < 0:
        raise exceptions.AuthenticationFailed('Invalid initData auth_date.')
    if settings.WEBAPP_INIT_DATA_MAX_AGE and auth_date:
        if time.time() - auth_date > settings.WEBAPP_INIT_DATA_MAX_AGE:
            raise exceptions.AuthenticationFailed('initData has expired.')
    try:
        user_payload = json.loads(pairs.get('user', '{}'))
    except json.JSONDecodeError as error:
        raise exceptions.AuthenticationFailed(
            'Invalid initData user payload.'
        ) from error
    if not isinstance(user_payload, dict):
        raise exceptions.AuthenticationFailed('Invalid initData user payload.')
    if not user_payload.get('id'):
        raise exceptions.AuthenticationFailed(
            'initData user payload is missing.'
        )
    pairs['user'] = user_payload
    return pairs


def sync_customer_from_telegram_payload(payload: dict) -> TelegramAuthPayload:
    """Обновляет клиента по данным Telegram WebApp."""
    user_data = payload['user']
    customer, _ = Customer.objects.get_or_create(
        telegram_id=user_data['id'],
        defaults={
            'username': user_data.get('username', ''),
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'language_code': user_data.get('language_code', ''),
        },
    )
    fields_to_update = []
    for field, value in (
        ('username', user_data.get('username', '')),
        ('first_name', user_data.get('first_name', '')),
        ('last_name', user_data.get('last_name', '')),
        ('language_code', user_data.get('language_code', '')),
    ):
        if getattr(customer, field) != value:
            setattr(customer, field, value)
            fields_to_update.append(field)
    customer.last_seen_at = timezone.now()
    customer.save(
        update_fields=[*fields_to_update, 'last_seen_at', 'updated_at']
    )
    return TelegramAuthPayload(customer=customer, data=payload)


class TelegramWebAppAuthentication(BaseAuthentication):
    """Аутентифицирует запросы веб-приложения Telegram."""

    def authenticate(self, request):
        """Возвращает клиента по данным Telegram WebApp."""
        init_data = request.headers.get('X-Telegram-Init-Data')
        if not init_data:
            return None
        payload = validate_init_data(init_data)
        auth_payload = sync_customer_from_telegram_payload(payload)
        return auth_payload.customer, auth_payload.data
