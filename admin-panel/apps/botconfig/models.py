"""Модели приложения настроек бота."""

from django.db import models

from apps.core.models import SingletonModel, TimestampedModel


class RequiredChannel(TimestampedModel):
    """Хранит канал для обязательной подписки."""

    title = models.CharField('Название', max_length=255)
    chat_id = models.BigIntegerField('Chat ID', blank=True, null=True)
    username = models.CharField('Username', max_length=255, blank=True)
    invite_link = models.URLField('Ссылка на вступление', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    sort_order = models.PositiveIntegerField('Порядок сортировки', default=0)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('sort_order', 'title')
        verbose_name = 'Канал/группа для подписки'
        verbose_name_plural = 'Каналы/группы для подписки'

    def __str__(self):
        """Возвращает название канала для админки."""
        return self.title

    @property
    def subscription_url(self):
        """Собирает ссылку для подписки на канал."""
        if self.invite_link:
            return self.invite_link
        if self.username:
            username = self.username.removeprefix('@')
            return f'https://t.me/{username}'
        return ''


class BotSettings(SingletonModel):
    """Хранит глобальные настройки бота."""

    admin_chat_id = models.BigIntegerField(
        'ID админ-чата', blank=True, null=True
    )
    catalog_webapp_url = models.URLField('URL WebApp', blank=True)
    help_text = models.TextField(
        'Текст помощи',
        blank=True,
        default=(
            'Используйте /catalog для просмотра каталога и /cart для корзины.'
        ),
    )
    subscription_message = models.TextField(
        'Сообщение о подписке',
        blank=True,
        default=(
            'Для продолжения подпишитесь на обязательные каналы '
            'и нажмите кнопку проверки.'
        ),
    )

    class Meta:
        """Задает параметры отображения модели."""

        verbose_name = 'Настройки бота'
        verbose_name_plural = 'Настройки бота'

    def __str__(self):
        """Возвращает название набора настроек."""
        return 'Настройки бота'
