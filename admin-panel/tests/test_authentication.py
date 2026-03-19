"""Тесты аутентификации Telegram WebApp."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from apps.api.authentication import validate_init_data
from rest_framework import exceptions


def build_signed_init_data(
    *,
    bot_token: str,
    auth_date: str | None = None,
    user: str | None = None,
) -> str:
    """Собирает корректно подписанный initData."""
    payload = {
        'auth_date': auth_date or str(int(time.time())),
        'user': user
        or json.dumps(
            {
                'id': 1,
                'username': 'test_user',
                'first_name': 'Иван',
            },
            ensure_ascii=True,
            separators=(',', ':'),
        ),
    }
    data_check_string = '\n'.join(
        f'{key}={value}' for key, value in sorted(payload.items())
    )
    secret_key = hmac.new(
        b'WebAppData',
        bot_token.encode(),
        hashlib.sha256,
    ).digest()
    payload['hash'] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(payload)


@pytest.mark.django_db
def test_validate_init_data_rejects_invalid_auth_date(settings):
    """Проверяет некорректный срок авторизации."""
    settings.TELEGRAM_BOT_TOKEN = 'test-token'
    init_data = build_signed_init_data(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        auth_date='broken',
    )

    with pytest.raises(
        exceptions.AuthenticationFailed,
        match='Invalid initData auth_date.',
    ):
        validate_init_data(init_data)


@pytest.mark.django_db
def test_validate_init_data_rejects_invalid_user_payload(settings):
    """Проверяет некорректные данные пользователя."""
    settings.TELEGRAM_BOT_TOKEN = 'test-token'
    init_data = build_signed_init_data(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        user='{"id":1',
    )

    with pytest.raises(
        exceptions.AuthenticationFailed,
        match='Invalid initData user payload.',
    ):
        validate_init_data(init_data)
