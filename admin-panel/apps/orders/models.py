"""Модели приложения заказов."""

from decimal import Decimal

from django.db import models

from apps.core.models import TimestampedModel
from apps.customers.models import Customer


class OrderStatus(models.TextChoices):
    """Перечисляет состояния заказа."""

    AWAITING_PAYMENT = 'awaiting_payment', 'Ожидает оплаты'
    PAYMENT_REPORTED = 'payment_reported', 'Оплата подтверждается'
    PAID = 'paid', 'Оплачен'
    PROCESSING = 'processing', 'В обработке'
    SHIPPED = 'shipped', 'Отправлен'
    COMPLETED = 'completed', 'Завершен'
    CANCELLED = 'cancelled', 'Отменен'

    @classmethod
    def active_statuses(cls):
        """Возвращает статусы незавершенных заказов."""
        return (
            cls.AWAITING_PAYMENT,
            cls.PAYMENT_REPORTED,
            cls.PAID,
            cls.PROCESSING,
            cls.SHIPPED,
        )

    @classmethod
    def paid_statuses(cls):
        """Возвращает статусы после подтверждения оплаты."""
        return (
            cls.PAID,
            cls.PROCESSING,
            cls.SHIPPED,
            cls.COMPLETED,
        )


class NotificationEventType(models.TextChoices):
    """Перечисляет типы уведомлений по заказам."""

    NEW_ORDER = 'new_order', 'Новый заказ'
    ORDER_STATUS_UPDATED = 'order_status_updated', 'Статус заказа обновлен'


class NotificationEventStatus(models.TextChoices):
    """Перечисляет статусы обработки уведомления."""

    PENDING = 'pending', 'Ожидает отправки'
    PROCESSING = 'processing', 'В обработке'
    COMPLETED = 'completed', 'Отправлено'
    FAILED = 'failed', 'Ошибка'


class Order(TimestampedModel):
    """Хранит заказ клиента."""

    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        related_name='orders',
        on_delete=models.PROTECT,
    )
    status = models.CharField(
        'Статус',
        max_length=32,
        choices=OrderStatus.choices,
        default=OrderStatus.AWAITING_PAYMENT,
    )
    full_name = models.CharField('ФИО', max_length=255)
    phone = models.CharField('Телефон', max_length=32)
    address = models.TextField('Адрес доставки')
    total_amount = models.DecimalField(
        'Сумма', max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    payment_stub_id = models.CharField(
        'Идентификатор платежа', max_length=64, blank=True
    )
    status_changed_at = models.DateTimeField(
        'Дата смены статуса', auto_now=True
    )
    admin_note = models.TextField('Комментарий администратора', blank=True)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('-created_at',)
        indexes = [
            models.Index(
                fields=['status', '-created_at'],
                name='order_status_created_idx',
            )
        ]
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        """Возвращает номер и клиента заказа."""
        return f'Заказ #{self.pk}'


class OrderItem(TimestampedModel):
    """Хранит отдельную позицию заказа."""

    order = models.ForeignKey(
        Order,
        verbose_name='Заказ',
        related_name='items',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        'catalog.Product',
        verbose_name='Товар',
        related_name='order_items',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    product_title = models.CharField('Название товара', max_length=255)
    product_price = models.DecimalField(
        'Цена товара', max_digits=10, decimal_places=2
    )
    quantity = models.PositiveIntegerField('Количество', default=1)

    class Meta:
        """Задает параметры отображения модели."""

        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        """Возвращает подпись позиции заказа."""
        return f'{self.product_title} x {self.quantity}'

    @property
    def line_total(self):
        """Возвращает стоимость позиции заказа."""
        return self.product_price * self.quantity


class NotificationEvent(TimestampedModel):
    """Хранит событие для отправки уведомления."""

    event_type = models.CharField(
        'Тип события', max_length=64, choices=NotificationEventType.choices
    )
    status = models.CharField(
        'Статус',
        max_length=32,
        choices=NotificationEventStatus.choices,
        default=NotificationEventStatus.PENDING,
    )
    order = models.ForeignKey(
        Order,
        verbose_name='Заказ',
        related_name='notifications',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        related_name='notifications',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    payload = models.JSONField('Payload', default=dict, blank=True)
    processed_at = models.DateTimeField('Обработан', blank=True, null=True)
    error_message = models.TextField('Ошибка', blank=True)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('created_at',)
        indexes = [
            models.Index(
                fields=['status', 'created_at'],
                name='notif_status_created_idx',
            ),
            models.Index(
                fields=['status', 'updated_at'],
                name='notif_status_updated_idx',
            ),
        ]
        verbose_name = 'Событие уведомления'
        verbose_name_plural = 'События уведомлений'

    def __str__(self):
        """Возвращает подпись события уведомления."""
        return f'{self.event_type} #{self.pk}'
