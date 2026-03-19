"""Сигналы, связанные с изменением заказов."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.orders.models import NotificationEvent, NotificationEventType, Order


@receiver(pre_save, sender=Order)
def remember_previous_status(sender, instance, **kwargs):
    """Сохраняет прошлый статус перед изменением."""
    if not instance.pk:
        return
    previous = sender.objects.only('status').filter(pk=instance.pk).first()
    instance._previous_status = previous.status if previous else None


@receiver(post_save, sender=Order)
def enqueue_order_notifications(sender, instance, created, **kwargs):
    """Создает события для отправки уведомлений."""
    if created:
        NotificationEvent.objects.create(
            event_type=NotificationEventType.NEW_ORDER,
            order=instance,
            customer=instance.customer,
            payload={'status': instance.status},
        )
        return

    previous_status = getattr(instance, '_previous_status', None)
    if previous_status and previous_status != instance.status:
        NotificationEvent.objects.create(
            event_type=NotificationEventType.ORDER_STATUS_UPDATED,
            order=instance,
            customer=instance.customer,
            payload={
                'previous_status': previous_status,
                'status': instance.status,
            },
        )
