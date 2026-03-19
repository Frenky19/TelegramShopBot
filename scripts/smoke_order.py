"""Smoke-скрипт для быстрой проверки оформления заказа."""

import argparse
import json
import os
import sys
from typing import Any
from urllib import error, request

DEFAULT_BASE_URL = 'http://localhost:8000'
DEFAULT_SERVICE_TOKEN = 'dev-service-token'
DEFAULT_SMOKE_TELEGRAM_ID = 2000000001
DEFAULT_SMOKE_QUANTITY = 2
DEFAULT_SMOKE_FULL_NAME = 'Тестовый пользователь'
DEFAULT_SMOKE_ADDRESS = 'Москва, Тестовая улица, 1'
DEFAULT_SMOKE_USERNAME = 'testovyy_zakaz'
DEFAULT_SMOKE_FIRST_NAME = 'Тестовый'
DEFAULT_SMOKE_LAST_NAME = 'Пользователь'
DEFAULT_SMOKE_PHONE = '79990000000'
DEFAULT_SMOKE_LANGUAGE_CODE = 'ru'
DEFAULT_NOTIFICATION_CLAIM_LIMIT = 50


def parse_args() -> argparse.Namespace:
    """Разбирает параметры запуска smoke-скрипта."""
    parser = argparse.ArgumentParser(
        description='Проверяет сценарий оформления заказа через service API.'
    )
    parser.add_argument(
        '--base-url',
        default=os.getenv('SMOKE_BASE_URL', DEFAULT_BASE_URL),
        help='Базовый адрес backend API.',
    )
    parser.add_argument(
        '--service-token',
        default=os.getenv(
            'INTERNAL_SERVICE_TOKEN',
            DEFAULT_SERVICE_TOKEN,
        ),
        help='Сервисный токен для внутренних endpoints.',
    )
    parser.add_argument(
        '--telegram-id',
        type=int,
        default=DEFAULT_SMOKE_TELEGRAM_ID,
        help='Telegram ID тестового клиента.',
    )
    parser.add_argument(
        '--quantity',
        type=int,
        default=DEFAULT_SMOKE_QUANTITY,
        help='Количество товара для smoke-заказа.',
    )
    parser.add_argument(
        '--full-name',
        default=DEFAULT_SMOKE_FULL_NAME,
        help='ФИО получателя для тестового заказа.',
    )
    parser.add_argument(
        '--address',
        default=DEFAULT_SMOKE_ADDRESS,
        help='Адрес доставки для тестового заказа.',
    )
    parser.add_argument(
        '--skip-complete',
        action='store_true',
        help='Оставляет заказ в статусе "Оплата подтверждается".',
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Не удаляет тестовые данные после завершения скрипта.',
    )
    return parser.parse_args()


class SmokeRequestError(RuntimeError):
    """Описывает ошибку HTTP-запроса во время smoke-проверки."""

    def __init__(
        self,
        method: str,
        path: str,
        *,
        status_code: int | None = None,
        detail: str = '',
    ) -> None:
        """Сохраняет метод, путь и код ошибки запроса."""
        self.method = method
        self.path = path
        self.status_code = status_code
        self.detail = detail
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        """Собирает человекочитаемый текст ошибки запроса."""
        if self.status_code is None:
            return (
                f'{self.method} {self.path} завершился ошибкой: '
                f'{self.detail}'
            )
        return (
            f'{self.method} {self.path} завершился ошибкой '
            f'{self.status_code}: {self.detail}'
        )


class SmokeClient:
    """Выполняет запросы к service API для smoke-проверки."""

    def __init__(self, *, base_url: str, service_token: str) -> None:
        """Сохраняет адрес backend-а и сервисный токен."""
        self.base_url = base_url.rstrip('/')
        self.service_token = service_token

    def request(self, method: str, path: str, **kwargs) -> Any:
        """Отправляет авторизованный запрос к service API."""
        return self._perform_request(
            method,
            path,
            headers={
                'X-Service-Token': self.service_token,
                'Content-Type': 'application/json',
            },
            **kwargs,
        )

    def public_request(self, method: str, path: str, **kwargs) -> Any:
        """Отправляет публичный запрос без сервисного токена."""
        return self._perform_request(method, path, headers={}, **kwargs)

    def _perform_request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        **kwargs,
    ) -> Any:
        """Подготавливает HTTP-запрос и читает JSON-ответ."""
        data = kwargs.get('json')
        payload = None
        if data is not None:
            payload = json.dumps(data).encode('utf-8')
        req = request.Request(
            url=f'{self.base_url}{path}',
            data=payload,
            method=method,
            headers=headers,
        )
        try:
            with request.urlopen(req, timeout=20) as response:
                body = response.read()
        except error.HTTPError as http_error:
            detail = http_error.read().decode('utf-8', errors='replace')
            raise SmokeRequestError(
                method,
                path,
                status_code=http_error.code,
                detail=detail,
            ) from http_error
        except error.URLError as url_error:
            raise SmokeRequestError(
                method,
                path,
                detail=str(url_error.reason),
            ) from url_error
        if not body:
            return {}
        return json.loads(body.decode('utf-8'))


def customer_exists(client: SmokeClient, telegram_id: int) -> bool:
    """Проверяет, создан ли клиент с указанным Telegram ID."""
    try:
        client.request('GET', f'/api/service/cart/{telegram_id}/')
    except SmokeRequestError as error:
        if error.status_code == 404:
            return False
        raise
    return True


def claim_and_complete_notifications(client: SmokeClient) -> int:
    """Закрывает уведомления, созданные во время smoke-прогона."""
    claimed = (
        client.request(
            'POST',
            '/api/service/notifications/claim/',
            json={'limit': DEFAULT_NOTIFICATION_CLAIM_LIMIT},
        )
        or []
    )
    for notification in claimed:
        client.request(
            'POST',
            f'/api/service/notifications/{notification["id"]}/complete/',
        )
    return len(claimed)


def cleanup_smoke_data(
    client: SmokeClient,
    *,
    telegram_id: int,
    order_id: int | None,
    delete_customer: bool,
) -> dict[str, Any]:
    """Удаляет тестовые данные, созданные во время smoke-прогона."""
    payload: dict[str, Any] = {
        'telegram_id': telegram_id,
        'delete_customer': delete_customer,
    }
    if order_id is not None:
        payload['order_id'] = order_id
    return client.request(
        'POST',
        '/api/service/smoke/cleanup/',
        json=payload,
    )


def run_smoke_scenario(
    client: SmokeClient,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Выполняет сценарий заказа и возвращает итоговые данные."""
    products_payload = client.public_request('GET', '/api/catalog/products/')
    products = products_payload.get('results', [])
    if not products:
        raise RuntimeError(
            'Каталог пуст. Сначала выполните команду seed_demo_data.'
        )
    product = products[0]
    client.request(
        'POST',
        '/api/service/customers/sync/',
        json={
            'telegram_id': args.telegram_id,
            'username': DEFAULT_SMOKE_USERNAME,
            'first_name': DEFAULT_SMOKE_FIRST_NAME,
            'last_name': DEFAULT_SMOKE_LAST_NAME,
            'phone': DEFAULT_SMOKE_PHONE,
            'language_code': DEFAULT_SMOKE_LANGUAGE_CODE,
        },
    )
    client.request(
        'POST',
        '/api/service/cart/clear/',
        json={'telegram_id': args.telegram_id},
    )
    client.request(
        'POST',
        '/api/service/cart/items/',
        json={
            'telegram_id': args.telegram_id,
            'product_id': product['id'],
            'mode': 'increment',
            'delta': args.quantity,
        },
    )
    cart = client.request('GET', f'/api/service/cart/{args.telegram_id}/')
    order = client.request(
        'POST',
        '/api/service/orders/checkout/',
        json={
            'telegram_id': args.telegram_id,
            'full_name': args.full_name,
            'address': args.address,
        },
    )
    payment_reported = client.request(
        'POST',
        f'/api/service/orders/{order["id"]}/mark-paid/',
    )
    processing = None
    completed = None
    if not args.skip_complete:
        processing = client.request(
            'POST',
            f'/api/service/orders/{order["id"]}/status/',
            json={'status': 'processing'},
        )
        completed = client.request(
            'POST',
            f'/api/service/orders/{order["id"]}/status/',
            json={'status': 'completed'},
        )
    notifications_completed = claim_and_complete_notifications(client)
    return {
        'заказ_id': order['id'],
        'товар_id': product['id'],
        'товар': product['title'],
        'количество': args.quantity,
        'сумма_корзины': cart['total_amount'],
        'идентификатор_платежа': order['payment_stub_id'],
        'статус_после_подтверждения_оплаты': payment_reported['status'],
        'статус_после_обработки': (
            processing['status'] if processing else None
        ),
        'финальный_статус': (
            completed['status']
            if completed
            else payment_reported['status']
        ),
        'закрыто_уведомлений': notifications_completed,
    }


def main() -> int:
    """Запускает smoke-проверку оформления заказа."""
    args = parse_args()
    client = SmokeClient(
        base_url=args.base_url,
        service_token=args.service_token,
    )
    customer_was_present = customer_exists(client, args.telegram_id)
    result = {}
    order_id = None
    try:
        result = run_smoke_scenario(client, args)
        order_id = result['заказ_id']
    except Exception:
        if not args.no_cleanup:
            try:
                cleanup_smoke_data(
                    client,
                    telegram_id=args.telegram_id,
                    order_id=order_id,
                    delete_customer=not customer_was_present,
                )
            except Exception as cleanup_error:
                print(
                    f'Автоочистка завершилась ошибкой: {cleanup_error}',
                    file=sys.stderr,
                )
        raise
    if not args.no_cleanup:
        result['очистка'] = cleanup_smoke_data(
            client,
            telegram_id=args.telegram_id,
            order_id=order_id,
            delete_customer=not customer_was_present,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1)
