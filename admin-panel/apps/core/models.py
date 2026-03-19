"""Модели приложения базовых компонентов."""

from django.db import models


class TimestampedModel(models.Model):
    """Добавляет поля времени создания и обновления."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Задает параметры отображения модели."""

        abstract = True


class SingletonModel(TimestampedModel):
    """Ограничивает модель одной записью."""

    singleton_pk = 1

    class Meta:
        """Задает параметры отображения модели."""

        abstract = True

    def save(self, *args, **kwargs):
        """Принудительно сохраняет объект с фиксированным PK."""
        self.pk = self.singleton_pk
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Возвращает или создает единственную запись модели."""
        instance, _ = cls.objects.get_or_create(pk=cls.singleton_pk)
        return instance
