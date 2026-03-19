"""Настройки Django admin для приложения заказов."""

from io import BytesIO

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from openpyxl import Workbook

from apps.orders.models import NotificationEvent, Order, OrderItem, OrderStatus


class OrderItemInline(admin.TabularInline):
    """Показывает состав заказа в форме админки."""

    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_title', 'product_price', 'quantity')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Настраивает список заказов и экспорт."""

    change_list_template = 'admin/orders/order/change_list.html'
    list_display = ('id', 'customer', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = (
        'id',
        'customer__telegram_id',
        'customer__username',
        'full_name',
        'phone',
    )
    readonly_fields = (
        'payment_stub_id',
        'created_at',
        'updated_at',
        'status_changed_at',
    )
    list_select_related = ('customer',)
    inlines = [OrderItemInline]

    def get_urls(self):
        """Подключает URL для экспорта оплаченных заказов."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'export-paid/',
                self.admin_site.admin_view(self.export_paid_orders_view),
                name='orders_order_export_paid',
            )
        ]
        return custom_urls + urls

    def export_paid_orders_view(self, request):
        """Формирует Excel-файл с оплаченными заказами."""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Paid Orders'
        sheet.append(
            [
                'Order ID',
                'Customer',
                'Phone',
                'Address',
                'Status',
                'Total',
                'Created',
            ]
        )
        orders = (
            Order.objects.select_related('customer')
            .filter(status__in=OrderStatus.paid_statuses())
            .order_by('-created_at')
        )
        for order in orders:
            sheet.append(
                [
                    order.pk,
                    order.customer.display_name,
                    order.phone,
                    order.address,
                    order.get_status_display(),
                    str(order.total_amount),
                    order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                ]
            )
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = (
            'attachment; filename="paid_orders.xlsx"'
        )
        return response


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    """Настраивает просмотр очереди уведомлений."""

    list_display = (
        'id',
        'event_type',
        'status',
        'customer',
        'order',
        'created_at',
    )
    list_filter = ('event_type', 'status')
    search_fields = (
        'order__id',
        'customer__telegram_id',
        'customer__username',
    )
    readonly_fields = ('processed_at', 'created_at', 'updated_at')
