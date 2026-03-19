"""Клиент и ошибки для работы бота с backend API."""

import asyncio
import time
from typing import Any

import httpx

from app.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_NOTIFICATION_CLAIM_LIMIT,
    DEFAULT_SETTINGS_CACHE_TTL_SECONDS,
    MAX_NOTIFICATION_ERROR_LENGTH,
)


class BackendAPIError(RuntimeError):
    """Описывает ошибку обращения к внутреннему API."""


def format_error_payload(payload: Any) -> str:
    """Собирает читаемый текст ошибки из payload."""
    if isinstance(payload, dict):
        messages = [format_error_payload(value) for value in payload.values()]
        return '\n'.join(message for message in messages if message).strip()
    if isinstance(payload, list):
        messages = [format_error_payload(value) for value in payload]
        return '\n'.join(message for message in messages if message).strip()
    if payload is None:
        return ''
    return str(payload).strip()


class BackendClient:
    """Инкапсулирует запросы бота к backend API."""

    def __init__(
        self,
        *,
        backend_url: str,
        media_base_url: str,
        service_token: str,
        settings_cache_ttl: int = DEFAULT_SETTINGS_CACHE_TTL_SECONDS,
    ) -> None:
        """Создает HTTP-клиент и кэш настроек."""
        self.backend_url = backend_url.rstrip('/')
        self.media_base_url = media_base_url.rstrip('/')
        self.service_token = service_token
        self.settings_cache_ttl = settings_cache_ttl
        self._client = httpx.AsyncClient(
            base_url=self.backend_url,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        self._settings_cache: dict[str, Any] | None = None
        self._settings_cache_at = 0.0
        self._settings_lock = asyncio.Lock()

    async def close(self) -> None:
        """Закрывает открытый HTTP-клиент."""
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *, service: bool = False, **kwargs
    ) -> Any:
        """Выполняет запрос к backend и обрабатывает ошибки."""
        headers = kwargs.pop('headers', {})
        if service:
            headers['X-Service-Token'] = self.service_token
        try:
            response = await self._client.request(
                method, path, headers=headers, **kwargs
            )
        except httpx.HTTPError as error:
            raise BackendAPIError(
                f'{method} {path} failed: {error}'
            ) from error
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            message = (
                format_error_payload(payload)
                or f'{method} {path} failed with status {response.status_code}'
            )
            raise BackendAPIError(message)
        if not response.content:
            return {}
        return response.json()

    async def _public_get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        """Выполняет публичный GET к backend."""
        return await self._request('GET', path, params=params)

    async def sync_customer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Синхронизирует клиента с backend."""
        return await self._request(
            'POST', '/api/service/customers/sync/', service=True, json=payload
        )

    async def get_settings(self, *, force: bool = False) -> dict[str, Any]:
        """Читает и кэширует настройки бота."""
        now = time.monotonic()
        if (
            not force
            and self._settings_cache
            and now - self._settings_cache_at < self.settings_cache_ttl
        ):
            return self._settings_cache
        async with self._settings_lock:
            now = time.monotonic()
            if (
                not force
                and self._settings_cache
                and now - self._settings_cache_at < self.settings_cache_ttl
            ):
                return self._settings_cache
            self._settings_cache = await self._request(
                'GET', '/api/service/settings/', service=True
            )
            self._settings_cache_at = now
            return self._settings_cache

    async def get_categories(self) -> list[dict[str, Any]]:
        """Получает дерево категорий каталога."""
        return await self._public_get('/api/catalog/categories/')

    async def get_products(
        self,
        *,
        category_id: int | None = None,
        page: int = 1,
        search: str = '',
    ) -> dict[str, Any]:
        """Получает страницу товаров с фильтрами."""
        params: dict[str, Any] = {'page': page}
        if category_id:
            params['category'] = category_id
        if search:
            params['search'] = search
        return await self._public_get('/api/catalog/products/', params=params)

    async def get_product(self, product_id: int) -> dict[str, Any]:
        """Получает полную карточку товара."""
        return await self._public_get(f'/api/catalog/products/{product_id}/')

    async def get_faq(self, query: str = '') -> list[dict[str, Any]]:
        """Получает ответы для встроенного поиска."""
        return await self._public_get(
            '/api/faq/inline/', params={'query': query}
        )

    async def get_cart(self, telegram_id: int) -> dict[str, Any]:
        """Получает корзину клиента по Telegram ID."""
        return await self._request(
            'GET', f'/api/service/cart/{telegram_id}/', service=True
        )

    async def update_cart_item(
        self,
        *,
        telegram_id: int,
        product_id: int,
        mode: str = 'increment',
        delta: int | None = None,
        quantity: int | None = None,
    ) -> dict[str, Any]:
        """Меняет позицию корзины через сервисный API."""
        payload: dict[str, Any] = {
            'telegram_id': telegram_id,
            'product_id': product_id,
            'mode': mode,
        }
        if delta is not None:
            payload['delta'] = delta
        if quantity is not None:
            payload['quantity'] = quantity
        return await self._request(
            'POST', '/api/service/cart/items/', service=True, json=payload
        )

    async def clear_cart(self, telegram_id: int) -> dict[str, Any]:
        """Полностью очищает корзину клиента."""
        return await self._request(
            'POST',
            '/api/service/cart/clear/',
            service=True,
            json={'telegram_id': telegram_id},
        )

    async def checkout(
        self, *, telegram_id: int, full_name: str, address: str
    ) -> dict[str, Any]:
        """Создает заказ через сервисный API."""
        return await self._request(
            'POST',
            '/api/service/orders/checkout/',
            service=True,
            json={
                'telegram_id': telegram_id,
                'full_name': full_name,
                'address': address,
            },
        )

    async def mark_paid(self, order_id: int) -> dict[str, Any]:
        """Отправляет отметку об оплате заказа."""
        return await self._request(
            'POST', f'/api/service/orders/{order_id}/mark-paid/', service=True
        )

    async def set_order_status(
        self, order_id: int, status: str
    ) -> dict[str, Any]:
        """Меняет статус заказа в backend."""
        return await self._request(
            'POST',
            f'/api/service/orders/{order_id}/status/',
            service=True,
            json={'status': status},
        )

    async def get_active_orders(self) -> list[dict[str, Any]]:
        """Получает активные заказы для админ-чата."""
        return await self._request(
            'GET', '/api/service/orders/active/', service=True
        )

    async def get_customer_active_orders(
        self, telegram_id: int
    ) -> list[dict[str, Any]]:
        """Получает активные заказы конкретного клиента."""
        return await self._request(
            'GET',
            f'/api/service/orders/customer/{telegram_id}/active/',
            service=True,
        )

    async def claim_notifications(
        self,
        limit: int = DEFAULT_NOTIFICATION_CLAIM_LIMIT,
    ) -> list[dict[str, Any]]:
        """Забирает порцию уведомлений для отправки."""
        return await self._request(
            'POST',
            '/api/service/notifications/claim/',
            service=True,
            json={'limit': limit},
        )

    async def complete_notification(self, notification_id: int) -> None:
        """Помечает уведомление обработанным."""
        await self._request(
            'POST',
            f'/api/service/notifications/{notification_id}/complete/',
            service=True,
        )

    async def fail_notification(
        self, notification_id: int, error_message: str
    ) -> None:
        """Сохраняет ошибку отправки уведомления."""
        await self._request(
            'POST',
            f'/api/service/notifications/{notification_id}/fail/',
            service=True,
            json={
                'error_message': error_message[:MAX_NOTIFICATION_ERROR_LENGTH]
            },
        )

    async def claim_broadcast(self) -> dict[str, Any]:
        """Забирает готовую рассылку в работу."""
        return await self._request(
            'POST', '/api/service/broadcasts/claim/', service=True
        )

    async def report_broadcast(
        self,
        broadcast_id: int,
        *,
        delivered_count: int,
        error_count: int,
        last_error: str = '',
    ) -> None:
        """Передает статистику отправленной рассылки."""
        await self._request(
            'POST',
            f'/api/service/broadcasts/{broadcast_id}/report/',
            service=True,
            json={
                'delivered_count': delivered_count,
                'error_count': error_count,
                'last_error': last_error[:MAX_NOTIFICATION_ERROR_LENGTH],
            },
        )

    async def download_media(self, relative_path: str) -> bytes:
        """Скачивает файл по относительному пути."""
        url = f'{self.media_base_url}{relative_path}'
        response = await self._client.get(url)
        response.raise_for_status()
        return response.content
