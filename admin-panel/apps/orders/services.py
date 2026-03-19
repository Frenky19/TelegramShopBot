"""Сервисные функции для оформления и обновления заказов."""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.customers.models import CartItem, Customer
from apps.orders.models import Order, OrderItem, OrderStatus


@transaction.atomic
def create_order_from_cart(
    customer: Customer, *, full_name: str, address: str
) -> Order:
    """Создает заказ по текущей корзине клиента."""
    cart_items = list(
        CartItem.objects.select_related('product')
        .select_for_update()
        .filter(customer=customer, product__is_active=True)
        .order_by('pk')
    )
    if not cart_items:
        raise ValueError('Корзина пуста')
    total_amount = sum(
        (item.product.price * item.quantity for item in cart_items),
        Decimal('0.00'),
    )
    order = Order.objects.create(
        customer=customer,
        full_name=full_name,
        phone=customer.phone,
        address=address,
        total_amount=total_amount,
        status=OrderStatus.AWAITING_PAYMENT,
    )
    order.payment_stub_id = f'PAY-{order.pk:06d}'
    order.save(update_fields=['payment_stub_id', 'updated_at'])
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=item.product,
                product_title=item.product.title,
                product_price=item.product.price,
                quantity=item.quantity,
            )
            for item in cart_items
        ]
    )
    CartItem.objects.filter(pk__in=[item.pk for item in cart_items]).delete()
    return order


def update_order_status(order: Order, status: str) -> Order:
    """Сохраняет новый статус заказа."""
    order.status = status
    order.status_changed_at = timezone.now()
    order.save(update_fields=['status', 'status_changed_at', 'updated_at'])
    return order


def mark_order_payment_reported(order: Order) -> Order:
    """Переводит заказ в ожидание подтверждения оплаты."""
    if order.status == OrderStatus.AWAITING_PAYMENT:
        return update_order_status(order, OrderStatus.PAYMENT_REPORTED)
    if order.status == OrderStatus.PAYMENT_REPORTED:
        raise ValidationError('Оплата по этому заказу уже отмечена.')
    raise ValidationError(
        'Статус оплаты уже обработан администратором, '
        'повторная отметка недоступна.'
    )
