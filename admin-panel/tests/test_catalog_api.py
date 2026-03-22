"""Тесты публичного API каталога."""

from decimal import Decimal

import pytest
from apps.catalog.models import Category, Product


@pytest.mark.django_db
def test_category_tree_returns_nested_children(client):
    """Возвращает дерево категорий с вложенными дочерними узлами."""
    root = Category.objects.create(title='Электроника')
    child = Category.objects.create(title='Аудио', parent=root)
    Category.objects.create(title='Наушники', parent=child)

    response = client.get('/api/catalog/categories/')

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]['id'] == root.id
    assert payload[0]['children'][0]['id'] == child.id
    assert payload[0]['children'][0]['children'][0]['title'] == 'Наушники'


@pytest.mark.django_db
def test_product_filter_by_parent_category_includes_descendants(client):
    """Фильтр по родителю включает товары из дочерних категорий."""
    root = Category.objects.create(title='Электроника')
    child = Category.objects.create(title='Аудио', parent=root)
    Product.objects.create(
        category=child,
        title='Наушники Nova',
        price=Decimal('12990.00'),
    )

    response = client.get(f'/api/catalog/products/?category={root.id}')

    assert response.status_code == 200
    payload = response.json()
    assert payload['count'] == 1
    assert payload['results'][0]['title'] == 'Наушники Nova'
