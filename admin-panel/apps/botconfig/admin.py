"""Настройки Django admin для приложения настроек бота."""

from django.contrib import admin

from apps.botconfig.models import BotSettings, RequiredChannel


@admin.register(RequiredChannel)
class RequiredChannelAdmin(admin.ModelAdmin):
    """Настраивает список обязательных каналов подписки."""

    list_display = ('title', 'chat_id', 'username', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('title', 'username', 'chat_id')


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    """Настраивает глобальные параметры бота."""

    def has_add_permission(self, request):
        """Запрещает создавать вторую запись настроек."""
        if BotSettings.objects.exists():
            return False
        return super().has_add_permission(request)
