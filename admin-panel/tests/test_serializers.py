"""Тесты сериализаторов backend API."""

import pytest
from apps.api.serializers import (
    CheckoutInputSerializer,
    ServiceCartItemSerializer,
)


@pytest.mark.django_db
def test_checkout_input_serializer_normalizes_values():
    """Проверяет нормализацию данных оформления."""
    serializer = CheckoutInputSerializer(
        data={
            'full_name': '  Иван   Иванов  ',
            'address': '  Москва, Тестовая улица, 1  ',
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['full_name'] == 'Иван Иванов'
    assert serializer.validated_data['address'] == 'Москва, Тестовая улица, 1'


@pytest.mark.django_db
def test_checkout_input_serializer_rejects_blank_full_name():
    """Проверяет пустое значение ФИО."""
    serializer = CheckoutInputSerializer(
        data={
            'full_name': '   ',
            'address': 'Москва, Тестовая улица, 1',
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors == {'full_name': ['Введите ФИО.']}


@pytest.mark.django_db
def test_service_cart_item_serializer_requires_quantity_for_set_mode():
    """Проверяет количество для режима замены."""
    serializer = ServiceCartItemSerializer(
        data={
            'telegram_id': 1,
            'product_id': 2,
            'mode': 'set',
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors == {
        'quantity': ['Передайте количество для режима set.']
    }


@pytest.mark.django_db
def test_service_cart_item_serializer_rejects_zero_delta():
    """Проверяет запрет нулевого изменения количества."""
    serializer = ServiceCartItemSerializer(
        data={
            'telegram_id': 1,
            'product_id': 2,
            'mode': 'increment',
            'delta': 0,
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors == {
        'delta': ['Изменение количества не может быть равно 0.']
    }
