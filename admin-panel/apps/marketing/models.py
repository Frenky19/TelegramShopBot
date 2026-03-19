"""Модели приложения маркетинга."""

from django.db import models

from apps.core.models import TimestampedModel


class FAQ(TimestampedModel):
    """Хранит вопрос и ответ для подсказок."""

    question = models.CharField('Вопрос', max_length=255)
    answer = models.TextField('Ответ')
    is_active = models.BooleanField('Активен', default=True)
    is_popular = models.BooleanField('Популярный', default=False)
    sort_order = models.PositiveIntegerField('Порядок сортировки', default=0)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('sort_order', 'question')
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'

    def __str__(self):
        """Возвращает строковое представление объекта."""
        return self.question


class BroadcastStatus(models.TextChoices):
    """Перечисляет этапы жизненного цикла рассылки."""

    DRAFT = 'draft', 'Черновик'
    READY = 'ready', 'Готово'
    SENDING = 'sending', 'Отправляется'
    SENT = 'sent', 'Отправлено'


class Broadcast(TimestampedModel):
    """Хранит параметры и статистику рассылки."""

    title = models.CharField('Название', max_length=255)
    text = models.TextField('Текст')
    image = models.ImageField(
        'Картинка', upload_to='broadcasts/%Y/%m/%d', blank=True, null=True
    )
    status = models.CharField(
        'Статус',
        max_length=16,
        choices=BroadcastStatus.choices,
        default=BroadcastStatus.DRAFT,
    )
    delivered_count = models.PositiveIntegerField('Доставлено', default=0)
    error_count = models.PositiveIntegerField('Ошибок', default=0)
    last_error = models.TextField('Последняя ошибка', blank=True)
    sent_at = models.DateTimeField('Отправлено в', blank=True, null=True)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('-created_at',)
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'

    def __str__(self):
        """Возвращает строковое представление объекта."""
        return self.title
