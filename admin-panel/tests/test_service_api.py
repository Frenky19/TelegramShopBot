"""Тесты сервисных endpoint-ов backend API."""

from decimal import Decimal

import pytest
from apps.customers.models import CartItem
from apps.orders.models import (
    NotificationEvent,
    NotificationEventType,
    Order,
    OrderStatus,
)
from django.urls import reverse


@pytest.mark.django_db
def test_service_checkout_creates_order_and_new_order_notification(
    service_client,
    customer,
    product,
):
    """Проверяет создание заказа и уведомления о нем."""
    CartItem.objects.create(customer=customer, product=product, quantity=2)

    response = service_client.post(
        reverse('service-checkout'),
        data={
            'telegram_id': customer.telegram_id,
            'full_name': 'Иван   Иванов',
            'address': 'Москва, Тестовая улица, 1',
        },
        format='json',
    )

    assert response.status_code == 201

    order = Order.objects.get(pk=response.json()['id'])
    assert order.status == OrderStatus.AWAITING_PAYMENT
    assert order.total_amount == Decimal('3980.00')
    assert not CartItem.objects.filter(customer=customer).exists()

    notification = NotificationEvent.objects.get(order=order)
    assert notification.event_type == NotificationEventType.NEW_ORDER
    assert notification.payload == {'status': OrderStatus.AWAITING_PAYMENT}


@pytest.mark.django_db
def test_service_order_status_creates_status_notification(
    service_client,
    order,
):
    """Проверяет уведомление о смене статуса."""
    response = service_client.post(
        reverse('service-order-status', args=[order.id]),
        data={'status': OrderStatus.PROCESSING},
        format='json',
    )

    assert response.status_code == 200

    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING

    notification = NotificationEvent.objects.filter(
        order=order,
        event_type=NotificationEventType.ORDER_STATUS_UPDATED,
    ).get()
    assert notification.payload == {
        'previous_status': OrderStatus.AWAITING_PAYMENT,
        'status': OrderStatus.PROCESSING,
    }


@pytest.mark.django_db
def test_service_mark_paid_rejects_status_regression(
    service_client,
    customer,
):
    """Проверяет запрет отката статуса оплаты."""
    order = Order.objects.create(
        customer=customer,
        full_name='Иван Иванов',
        phone=customer.phone,
        address='Москва, Тестовая улица, 1',
        total_amount=Decimal('1990.00'),
        status=OrderStatus.PROCESSING,
    )

    response = service_client.post(
        reverse('service-mark-paid', args=[order.id]),
        format='json',
    )

    assert response.status_code == 400

    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING
    assert 'повторная отметка недоступна' in str(response.json())


@pytest.mark.django_db
def test_service_smoke_cleanup_removes_test_data(
    service_client,
    customer,
    product,
):
    """Проверяет удаление корзины, заказа и тестового клиента."""
    cart_item = CartItem.objects.create(
        customer=customer,
        product=product,
        quantity=1,
    )
    order = Order.objects.create(
        customer=customer,
        full_name='Иван Иванов',
        phone=customer.phone,
        address='Москва, Тестовая улица, 1',
        total_amount=Decimal('1990.00'),
    )
    NotificationEvent.objects.create(
        customer=customer,
        event_type=NotificationEventType.ORDER_STATUS_UPDATED,
        payload={'status': OrderStatus.PROCESSING},
    )

    response = service_client.post(
        reverse('service-smoke-cleanup'),
        data={
            'telegram_id': customer.telegram_id,
            'order_id': order.id,
            'delete_customer': True,
        },
        format='json',
    )

    assert response.status_code == 200
    assert response.json() == {
        'deleted_cart_items': 1,
        'deleted_notifications': 2,
        'deleted_orders': 1,
        'deleted_customer': True,
    }
    assert not CartItem.objects.filter(pk=cart_item.pk).exists()
    assert not Order.objects.filter(pk=order.pk).exists()
    assert not customer.__class__.objects.filter(pk=customer.pk).exists()
    assert not NotificationEvent.objects.filter(customer=customer).exists()
