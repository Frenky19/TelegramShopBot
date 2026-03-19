"""Настройки Django admin для приложения маркетинга."""

from pathlib import Path

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.marketing.models import FAQ, Broadcast


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """Настраивает раздел вопросов и ответов."""

    list_display = ('question', 'is_active', 'is_popular', 'sort_order')
    list_filter = ('is_active', 'is_popular')
    search_fields = ('question', 'answer')


class BroadcastAdminForm(forms.ModelForm):
    """Проверяет данные формы рассылки."""

    class Meta:
        """Задает модель и поля формы."""

        model = Broadcast
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """Добавляет подсказку по поддерживаемым форматам."""
        super().__init__(*args, **kwargs)
        self.fields['image'].help_text = (
            'Используйте изображение в формате JPG, JPEG или PNG. '
            'Форматы вроде ICO не поддерживаются.'
        )

    def clean_image(self):
        """Проверяет расширение загруженного изображения."""
        image = self.cleaned_data.get('image')
        if not image:
            return image
        extension = Path(image.name).suffix.lower()
        allowed_extensions = {'.jpg', '.jpeg', '.png'}
        if extension not in allowed_extensions:
            allowed = ', '.join(
                sorted(ext.lstrip('.').upper() for ext in allowed_extensions)
            )
            raise ValidationError(
                f'Допустимые форматы изображения: {allowed}.'
            )
        return image


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    """Настраивает список и форму рассылок."""

    form = BroadcastAdminForm
    list_display = (
        'title',
        'status',
        'delivered_count',
        'error_count',
        'created_at',
        'sent_at',
    )
    list_filter = ('status',)
    search_fields = ('title', 'text')
    readonly_fields = (
        'delivered_count',
        'error_count',
        'last_error',
        'sent_at',
        'created_at',
        'updated_at',
    )
