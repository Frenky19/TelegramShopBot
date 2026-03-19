"""Настройки Django admin для приложения клиентов."""

from django.contrib import admin
from django.db.models import Count, Sum

from apps.customers.models import CartItem, Customer
from apps.orders.models import Order


class OrderInline(admin.TabularInline):
    """Показывает заказы клиента прямо в админке."""

    model = Order
    extra = 0
    can_delete = False
    fields = ('id', 'status', 'total_amount', 'created_at')
    readonly_fields = fields
    show_change_link = True


class CartItemInline(admin.TabularInline):
    """Показывает корзину клиента прямо в админке."""

    model = CartItem
    extra = 0
    fields = ('product', 'quantity', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Настраивает список клиентов и их статистику."""

    list_display = (
        'telegram_id',
        'username',
        'phone',
        'order_count',
        'order_total',
        'is_bot_admin',
    )
    search_fields = (
        'telegram_id',
        'username',
        'phone',
        'first_name',
        'last_name',
    )
    list_filter = ('is_bot_admin',)
    readonly_fields = ('created_at', 'updated_at', 'last_seen_at')
    inlines = [OrderInline, CartItemInline]

    def get_queryset(self, request):
        """Добавляет в список клиентов агрегаты по заказам."""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            _order_count=Count('orders'),
            _order_total=Sum('orders__total_amount'),
        )

    @admin.display(description='Заказов', ordering='_order_count')
    def order_count(self, obj):
        """Возвращает число заказов клиента."""
        return getattr(obj, '_order_count', 0)

    @admin.display(description='Сумма', ordering='_order_total')
    def order_total(self, obj):
        """Возвращает сумму оплаченных заказов клиента."""
        return getattr(obj, '_order_total', 0) or 0
