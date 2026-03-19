"""Тесты очереди уведомлений и рассылок."""

from datetime import timedelta

import pytest
from apps.customers.models import Customer
from apps.marketing.models import Broadcast, BroadcastStatus
from apps.orders.models import (
    NotificationEvent,
    NotificationEventStatus,
    NotificationEventType,
)
from django.urls import reverse
from django.utils import timezone


@pytest.mark.django_db
def test_service_claim_notifications_picks_pending_and_stale_processing(
    service_client,
    settings,
    order,
):
    """Проверяет захват новых и зависших уведомлений."""
    NotificationEvent.objects.all().delete()

    stale_time = timezone.now() - settings.NOTIFICATION_PROCESSING_TIMEOUT
    stale_time -= timedelta(seconds=1)

    pending_notification = NotificationEvent.objects.create(
        event_type=NotificationEventType.NEW_ORDER,
        order=order,
        customer=order.customer,
        payload={'status': order.status},
    )
    stale_processing = NotificationEvent.objects.create(
        event_type=NotificationEventType.ORDER_STATUS_UPDATED,
        order=order,
        customer=order.customer,
        status=NotificationEventStatus.PROCESSING,
        payload={
            'previous_status': 'awaiting_payment',
            'status': 'processing',
        },
    )
    recent_processing = NotificationEvent.objects.create(
        event_type=NotificationEventType.ORDER_STATUS_UPDATED,
        order=order,
        customer=order.customer,
        status=NotificationEventStatus.PROCESSING,
        payload={'status': 'paid'},
    )

    NotificationEvent.objects.filter(pk=stale_processing.pk).update(
        updated_at=stale_time
    )

    response = service_client.post(
        reverse('service-claim-notifications'),
        data={'limit': 10},
        format='json',
    )

    assert response.status_code == 200
    claimed_ids = {item['id'] for item in response.json()}
    assert claimed_ids == {
        pending_notification.id,
        stale_processing.id,
    }

    pending_notification.refresh_from_db()
    stale_processing.refresh_from_db()
    recent_processing.refresh_from_db()

    assert pending_notification.status == NotificationEventStatus.PROCESSING
    assert stale_processing.status == NotificationEventStatus.PROCESSING
    assert recent_processing.status == NotificationEventStatus.PROCESSING


@pytest.mark.django_db
def test_service_complete_notification_marks_it_completed(
    service_client,
    order,
):
    """Проверяет завершение уведомления."""
    notification = NotificationEvent.objects.create(
        event_type=NotificationEventType.NEW_ORDER,
        order=order,
        customer=order.customer,
        status=NotificationEventStatus.PROCESSING,
        error_message='Временная ошибка',
    )

    response = service_client.post(
        reverse('service-notification-complete', args=[notification.id]),
        format='json',
    )

    assert response.status_code == 200

    notification.refresh_from_db()
    assert notification.status == NotificationEventStatus.COMPLETED
    assert notification.processed_at is not None
    assert notification.error_message == ''


@pytest.mark.django_db
def test_service_fail_notification_marks_it_failed(service_client, order):
    """Проверяет перевод уведомления в ошибку."""
    notification = NotificationEvent.objects.create(
        event_type=NotificationEventType.NEW_ORDER,
        order=order,
        customer=order.customer,
        status=NotificationEventStatus.PROCESSING,
    )

    response = service_client.post(
        reverse('service-notification-fail', args=[notification.id]),
        data={'error_message': 'Telegram временно недоступен'},
        format='json',
    )

    assert response.status_code == 200

    notification.refresh_from_db()
    assert notification.status == NotificationEventStatus.FAILED
    assert notification.processed_at is not None
    assert notification.error_message == 'Telegram временно недоступен'


@pytest.mark.django_db
def test_service_claim_broadcast_marks_oldest_ready_as_sending(
    service_client,
    customer,
):
    """Проверяет захват ближайшей готовой рассылки."""
    second_customer = Customer.objects.create(
        telegram_id=987654321,
        username='second_user',
    )
    older_broadcast = Broadcast.objects.create(
        title='Первая рассылка',
        text='Текст первой рассылки',
        status=BroadcastStatus.READY,
    )
    newer_broadcast = Broadcast.objects.create(
        title='Вторая рассылка',
        text='Текст второй рассылки',
        status=BroadcastStatus.READY,
    )

    response = service_client.post(
        reverse('service-broadcast-claim'),
        format='json',
    )

    assert response.status_code == 200

    older_broadcast.refresh_from_db()
    newer_broadcast.refresh_from_db()

    assert response.json()['id'] == older_broadcast.id
    assert older_broadcast.status == BroadcastStatus.SENDING
    assert newer_broadcast.status == BroadcastStatus.READY
    assert set(response.json()['recipients']) == {
        customer.telegram_id,
        second_customer.telegram_id,
    }


@pytest.mark.django_db
def test_service_broadcast_report_marks_broadcast_sent(service_client):
    """Проверяет сохранение отчета по рассылке."""
    broadcast = Broadcast.objects.create(
        title='Готовая рассылка',
        text='Текст рассылки',
        status=BroadcastStatus.SENDING,
    )

    response = service_client.post(
        reverse('service-broadcast-report', args=[broadcast.id]),
        data={
            'delivered_count': 12,
            'error_count': 1,
            'last_error': 'chat not found',
        },
        format='json',
    )

    assert response.status_code == 200

    broadcast.refresh_from_db()
    assert broadcast.status == BroadcastStatus.SENT
    assert broadcast.delivered_count == 12
    assert broadcast.error_count == 1
    assert broadcast.last_error == 'chat not found'
    assert broadcast.sent_at is not None
