"""Модели приложения клиентов."""

from django.db import models
from django.db.models import Sum

from apps.catalog.models import Product
from apps.core.models import TimestampedModel


class Customer(TimestampedModel):
    """Хранит профиль клиента из Telegram."""

    telegram_id = models.BigIntegerField('Telegram ID', unique=True)
    username = models.CharField('Username', max_length=150, blank=True)
    first_name = models.CharField('Имя', max_length=150, blank=True)
    last_name = models.CharField('Фамилия', max_length=150, blank=True)
    phone = models.CharField('Телефон', max_length=32, blank=True)
    language_code = models.CharField('Язык', max_length=16, blank=True)
    is_bot_admin = models.BooleanField('Админ бота', default=False)
    last_seen_at = models.DateTimeField('Последняя активность', auto_now=True)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('-updated_at',)
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'

    def __str__(self):
        """Возвращает подпись клиента для админки."""
        return self.display_name

    @property
    def display_name(self):
        """Возвращает имя пользователя для интерфейса."""
        parts = [self.first_name, self.last_name]
        human_name = ' '.join(part for part in parts if part).strip()
        return human_name or self.username or str(self.telegram_id)

    @property
    def total_spent(self):
        """Считает общую сумму заказов клиента."""
        return self.orders.aggregate(total=Sum('total_amount'))['total'] or 0

    @property
    def is_authenticated(self):
        """Сообщает Django, что клиент аутентифицирован."""
        return True

    @property
    def is_anonymous(self):
        """Сообщает Django, что клиент не анонимный."""
        return False


class CartItem(TimestampedModel):
    """Хранит товар в корзине клиента."""

    customer = models.ForeignKey(
        Customer,
        verbose_name='Клиент',
        related_name='cart_items',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        related_name='cart_items',
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField('Количество', default=1)

    class Meta:
        """Задает параметры отображения модели."""

        unique_together = ('customer', 'product')
        ordering = ('-updated_at',)
        verbose_name = 'Позиция корзины'
        verbose_name_plural = 'Корзина'

    def __str__(self):
        """Возвращает подпись позиции корзины."""
        return (
            f'{self.customer.display_name} -> '
            f'{self.product.title} x {self.quantity}'
        )

    @property
    def line_total(self):
        """Возвращает стоимость позиции корзины."""
        return self.quantity * self.product.price
