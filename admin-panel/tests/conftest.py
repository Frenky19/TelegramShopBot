"""Фикстуры pytest для backend-тестов."""

from decimal import Decimal

import pytest
from apps.catalog.models import Category, Product
from apps.customers.models import Customer
from apps.orders.models import Order
from rest_framework.test import APIClient


@pytest.fixture
def service_client(settings):
    """Создает DRF-клиент с сервисным токеном."""
    client = APIClient()
    client.credentials(HTTP_X_SERVICE_TOKEN=settings.INTERNAL_SERVICE_TOKEN)
    return client


@pytest.fixture
def category():
    """Создает категорию для тестов."""
    return Category.objects.create(title='Тестовая категория')


@pytest.fixture
def product(category):
    """Создает товар для тестов."""
    return Product.objects.create(
        category=category,
        title='Тестовый товар',
        price=Decimal('1990.00'),
    )


@pytest.fixture
def customer():
    """Создает клиента для тестов."""
    return Customer.objects.create(
        telegram_id=123456789,
        username='test_user',
        first_name='Иван',
        last_name='Иванов',
        phone='+79990000000',
        language_code='ru',
    )


@pytest.fixture
def order(customer):
    """Создает заказ для тестов."""
    return Order.objects.create(
        customer=customer,
        full_name='Иван Иванов',
        phone=customer.phone,
        address='Москва, Тестовая улица, 1',
        total_amount=Decimal('1990.00'),
    )
