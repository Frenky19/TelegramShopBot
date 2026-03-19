"""Тесты сервисных функций заказов."""

from decimal import Decimal

import pytest
from apps.catalog.models import Product
from apps.customers.models import CartItem
from apps.orders.models import OrderStatus
from apps.orders.services import (
    create_order_from_cart,
    mark_order_payment_reported,
)
from rest_framework.exceptions import ValidationError


@pytest.mark.django_db
def test_create_order_from_cart_creates_items_and_clears_cart(
    category,
    customer,
    product,
):
    """Проверяет создание заказа и очистку корзины."""
    second_product = Product.objects.create(
        category=category,
        title='Второй товар',
        price=Decimal('500.00'),
    )
    CartItem.objects.create(customer=customer, product=product, quantity=2)
    CartItem.objects.create(
        customer=customer,
        product=second_product,
        quantity=3,
    )

    order = create_order_from_cart(
        customer,
        full_name='Иван   Иванов',
        address='Москва, Тестовая улица, 1',
    )

    assert order.status == OrderStatus.AWAITING_PAYMENT
    assert order.phone == customer.phone
    assert order.total_amount == Decimal('5480.00')
    assert order.payment_stub_id == f'PAY-{order.pk:06d}'
    assert order.items.count() == 2
    assert not CartItem.objects.filter(customer=customer).exists()


@pytest.mark.django_db
def test_mark_order_payment_reported_allows_only_single_transition(order):
    """Проверяет защиту от повторного подтверждения оплаты."""
    updated_order = mark_order_payment_reported(order)

    assert updated_order.status == OrderStatus.PAYMENT_REPORTED

    with pytest.raises(ValidationError, match='уже отмечена'):
        mark_order_payment_reported(updated_order)

    updated_order.status = OrderStatus.PROCESSING
    updated_order.save(update_fields=['status', 'updated_at'])

    with pytest.raises(ValidationError, match='повторная отметка недоступна'):
        mark_order_payment_reported(updated_order)
