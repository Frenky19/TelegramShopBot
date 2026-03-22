"""Представления публичного и сервисного API."""

from decimal import Decimal

from config.constants import DEFAULT_PAGE_SIZE
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.authentication import (
    sync_customer_from_telegram_payload,
    validate_init_data,
)
from apps.api.constants import (
    ACTIVE_ORDERS_LIMIT,
    FAQ_RESULTS_LIMIT,
)
from apps.api.permissions import HasServiceToken
from apps.api.serializers import (
    BotSettingsSerializer,
    BroadcastReportSerializer,
    BroadcastSerializer,
    CartSerializer,
    CategoryTreeSerializer,
    CheckoutInputSerializer,
    CustomerSerializer,
    FAQSerializer,
    NotificationClaimSerializer,
    NotificationFailSerializer,
    NotificationSerializer,
    OrderSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ServiceCartItemSerializer,
    ServiceCheckoutSerializer,
    ServiceOrderStatusSerializer,
    ServiceSmokeCleanupSerializer,
    ServiceSyncCustomerSerializer,
    TelegramCustomerReferenceSerializer,
    WebAppCartItemCreateSerializer,
    WebAppCartItemUpdateSerializer,
)
from apps.botconfig.models import BotSettings
from apps.catalog.models import Category, Product
from apps.customers.models import CartItem, Customer
from apps.marketing.models import FAQ, Broadcast, BroadcastStatus
from apps.orders.models import (
    NotificationEvent,
    NotificationEventStatus,
    Order,
    OrderStatus,
)
from apps.orders.services import (
    create_order_from_cart,
    mark_order_payment_reported,
    update_order_status,
)


def build_category_children_map(
    categories: list[Category],
) -> dict[int | None, list[Category]]:
    """Группирует категории по родителю в памяти."""
    children_map: dict[int | None, list[Category]] = {}
    for category in categories:
        children_map.setdefault(category.parent_id, []).append(category)
    return children_map


def collect_category_ids(
    category_id: int,
    children_map: dict[int | None, list[Category]],
) -> list[int]:
    """Собирает идентификаторы категории и всех потомков без новых запросов."""
    identifiers: list[int] = []
    pending = [category_id]
    while pending:
        current_id = pending.pop()
        identifiers.append(current_id)
        pending.extend(
            child.pk for child in children_map.get(current_id, [])
        )
    return identifiers


def serialize_cart(customer: Customer) -> dict:
    """Преобразует корзину клиента в ответ API."""
    items = list(
        CartItem.objects.select_related('product', 'product__category')
        .prefetch_related('product__images')
        .filter(customer=customer, product__is_active=True)
        .order_by('-updated_at')
    )
    total_amount = sum(
        (item.product.price * item.quantity for item in items),
        Decimal('0.00'),
    )
    return CartSerializer({'items': items, 'total_amount': total_amount}).data


def sync_or_update_cart_item(
    customer: Customer,
    product_id: int,
    *,
    quantity: int | None = None,
    delta: int | None = None,
):
    """Меняет количество товара в корзине клиента."""
    product = Product.objects.filter(pk=product_id, is_active=True).first()
    if not product:
        raise NotFound('Товар не найден.')
    cart_item, _ = CartItem.objects.get_or_create(
        customer=customer,
        product=product,
        defaults={'quantity': 0},
    )
    if delta is not None:
        cart_item.quantity += delta
    elif quantity is not None:
        cart_item.quantity = quantity
    else:
        raise ValidationError('Не передано новое количество.')

    if cart_item.quantity <= 0:
        cart_item.delete()
        return None
    cart_item.save(update_fields=['quantity', 'updated_at'])
    return cart_item


class DefaultPagination(PageNumberPagination):
    """Хранит настройки стандартной пагинации API."""

    page_size = DEFAULT_PAGE_SIZE


class CategoryTreeAPIView(APIView):
    """Отдает дерево активных категорий каталога."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Возвращает корневые категории каталога."""
        categories = list(
            Category.objects.filter(is_active=True).order_by(
                'parent_id',
                'sort_order',
                'title',
            )
        )
        children_map = build_category_children_map(categories)
        serializer = CategoryTreeSerializer(
            children_map.get(None, []),
            many=True,
            context={'category_children_map': children_map},
        )
        return Response(serializer.data)


class ProductListAPIView(ListAPIView):
    """Отдает список товаров с фильтрами и поиском."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        """Фильтрует товары по категории и строке поиска."""
        queryset = (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .prefetch_related('images')
        )
        category_id = self.request.query_params.get('category')
        if category_id:
            try:
                requested_category_id = int(category_id)
            except (TypeError, ValueError):
                requested_category_id = None
            active_categories = list(
                Category.objects.filter(is_active=True).only('id', 'parent_id')
            )
            available_category_ids = {
                category.pk for category in active_categories
            }
            if (
                requested_category_id is not None
                and requested_category_id in available_category_ids
            ):
                children_map = build_category_children_map(active_categories)
                queryset = queryset.filter(
                    category_id__in=collect_category_ids(
                        requested_category_id,
                        children_map,
                    )
                )
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )
        return queryset.order_by('sort_order', 'title')


class ProductDetailAPIView(RetrieveAPIView):
    """Отдает полную карточку одного товара."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ProductDetailSerializer
    queryset = (
        Product.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related('images')
    )


class FAQInlineAPIView(APIView):
    """Возвращает ответы для встроенного поиска."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Подбирает FAQ по запросу или популярности."""
        query = request.query_params.get('query', '').strip()
        queryset = FAQ.objects.filter(is_active=True)
        if query:
            queryset = queryset.filter(
                Q(question__icontains=query) | Q(answer__icontains=query)
            )
        else:
            queryset = queryset.filter(is_popular=True)
        serializer = FAQSerializer(
            queryset.order_by('sort_order', 'question')[:FAQ_RESULTS_LIMIT],
            many=True,
        )
        return Response(serializer.data)


class WebAppSessionAPIView(APIView):
    """Создает сессию клиента для Telegram WebApp."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Создает сессию клиента и возвращает стартовые данные."""
        init_data = request.data.get('initData') or request.headers.get(
            'X-Telegram-Init-Data'
        )
        payload = validate_init_data(init_data)
        auth_payload = sync_customer_from_telegram_payload(payload)
        settings_payload = BotSettingsSerializer(BotSettings.load()).data
        return Response(
            {
                'customer': CustomerSerializer(auth_payload.customer).data,
                'cart': serialize_cart(auth_payload.customer),
                'settings': settings_payload,
            }
        )


class WebAppCartAPIView(APIView):
    """Возвращает корзину авторизованного клиента."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Возвращает корзину текущего пользователя."""
        return Response(serialize_cart(request.user))


class WebAppCartItemAPIView(APIView):
    """Изменяет позиции корзины в Telegram WebApp."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Добавляет товар в корзину WebApp."""
        serializer = WebAppCartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        sync_or_update_cart_item(
            request.user,
            payload['product_id'],
            delta=payload['delta'],
        )
        return Response(serialize_cart(request.user))

    def patch(self, request, product_id: int):
        """Меняет количество товара в корзине WebApp."""
        serializer = WebAppCartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sync_or_update_cart_item(
            request.user,
            product_id,
            quantity=serializer.validated_data['quantity'],
        )
        return Response(serialize_cart(request.user))

    def delete(self, request, product_id: int):
        """Удаляет товар из корзины WebApp."""
        sync_or_update_cart_item(request.user, product_id, quantity=0)
        return Response(serialize_cart(request.user))


class WebAppCartClearAPIView(APIView):
    """Полностью очищает корзину WebApp."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Удаляет все позиции из корзины WebApp."""
        request.user.cart_items.all().delete()
        return Response(serialize_cart(request.user))


class WebAppCheckoutAPIView(APIView):
    """Оформляет заказ из корзины WebApp."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Оформляет заказ для авторизованного клиента."""
        if not request.user.phone:
            raise ValidationError(
                'Для оформления заказа требуется телефон из Telegram-профиля.'
            )
        serializer = CheckoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = create_order_from_cart(
                request.user,
                full_name=serializer.validated_data['full_name'],
                address=serializer.validated_data['address'],
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class ServiceSyncCustomerAPIView(APIView):
    """Синхронизирует клиента по данным Telegram."""

    permission_classes = [HasServiceToken]

    def post(self, request):
        """Создает или обновляет клиента по Telegram ID."""
        serializer = ServiceSyncCustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        customer, _ = Customer.objects.get_or_create(
            telegram_id=payload['telegram_id']
        )
        changed_fields = []
        for field in (
            'username',
            'first_name',
            'last_name',
            'language_code',
            'phone',
        ):
            value = payload.get(field)
            if value is not None and getattr(customer, field) != value:
                setattr(customer, field, value)
                changed_fields.append(field)
        customer.last_seen_at = timezone.now()
        customer.save(
            update_fields=[*changed_fields, 'last_seen_at', 'updated_at']
        )
        return Response(CustomerSerializer(customer).data)


class ServiceSettingsAPIView(APIView):
    """Возвращает настройки бота для внутренних сервисов."""

    permission_classes = [HasServiceToken]

    def get(self, request):
        """Возвращает текущие настройки бота."""
        serializer = BotSettingsSerializer(BotSettings.load())
        return Response(serializer.data)


class ServiceCartAPIView(APIView):
    """Возвращает корзину клиента по Telegram ID."""

    permission_classes = [HasServiceToken]

    def get_customer(self, telegram_id: int) -> Customer:
        """Находит клиента по Telegram ID."""
        customer = Customer.objects.filter(telegram_id=telegram_id).first()
        if not customer:
            raise NotFound('Клиент не найден.')
        return customer

    def get(self, request, telegram_id: int):
        """Возвращает корзину выбранного клиента."""
        customer = self.get_customer(telegram_id)
        return Response(serialize_cart(customer))


class ServiceCartItemAPIView(APIView):
    """Изменяет позиции корзины через сервисный API."""

    permission_classes = [HasServiceToken]

    def post(self, request):
        """Изменяет корзину клиента через сервисный запрос."""
        serializer = ServiceCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        customer = Customer.objects.filter(
            telegram_id=payload['telegram_id']
        ).first()
        if not customer:
            raise NotFound('Клиент не найден.')

        if payload['mode'] == 'set':
            sync_or_update_cart_item(
                customer,
                payload['product_id'],
                quantity=payload['quantity'],
            )
        else:
            sync_or_update_cart_item(
                customer,
                payload['product_id'],
                delta=payload['delta'],
            )
        return Response(serialize_cart(customer))


class ServiceCartClearAPIView(APIView):
    """Очищает корзину через сервисный API."""

    permission_classes = [HasServiceToken]

    def post(self, request):
        """Очищает корзину клиента по Telegram ID."""
        serializer = TelegramCustomerReferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = Customer.objects.filter(
            telegram_id=serializer.validated_data['telegram_id']
        ).first()
        if not customer:
            raise NotFound('Клиент не найден.')
        customer.cart_items.all().delete()
        return Response(serialize_cart(customer))


class ServiceCheckoutAPIView(APIView):
    """Оформляет заказ через сервисный API."""

    permission_classes = [HasServiceToken]

    def post(self, request):
        """Создает заказ по сервисному запросу."""
        serializer = ServiceCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        customer = Customer.objects.filter(
            telegram_id=payload['telegram_id']
        ).first()
        if not customer:
            raise NotFound('Клиент не найден.')
        if not customer.phone:
            raise ValidationError('У клиента не указан телефон.')
        try:
            order = create_order_from_cart(
                customer,
                full_name=payload['full_name'],
                address=payload['address'],
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class ServiceMarkPaidAPIView(APIView):
    """Помечает заказ как отмеченный пользователем."""

    permission_classes = [HasServiceToken]

    def post(self, request, order_id: int):
        """Отмечает оплату заказа от имени клиента."""
        order = get_object_or_404(
            Order.objects.select_related('customer'),
            pk=order_id,
        )
        mark_order_payment_reported(order)
        return Response(OrderSerializer(order).data)


class ServiceOrderStatusAPIView(APIView):
    """Меняет статус заказа через сервисный API."""

    permission_classes = [HasServiceToken]

    def post(self, request, order_id: int):
        """Меняет статус заказа от имени администратора."""
        order = get_object_or_404(
            Order.objects.select_related('customer'),
            pk=order_id,
        )
        serializer = ServiceOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_order_status(order, serializer.validated_data['status'])
        return Response(OrderSerializer(order).data)


class ServiceActiveOrdersAPIView(APIView):
    """Возвращает активные заказы магазина."""

    permission_classes = [HasServiceToken]

    def get(self, request):
        """Возвращает ограниченный список активных заказов."""
        queryset = (
            Order.objects.select_related('customer')
            .prefetch_related('items')
            .filter(status__in=OrderStatus.active_statuses())
        )
        serializer = OrderSerializer(
            queryset[:ACTIVE_ORDERS_LIMIT],
            many=True,
        )
        return Response(serializer.data)


class ServiceCustomerActiveOrdersAPIView(APIView):
    """Возвращает активные заказы клиента."""

    permission_classes = [HasServiceToken]

    def get(self, request, telegram_id: int):
        """Возвращает активные заказы конкретного клиента."""
        queryset = (
            Order.objects.select_related('customer')
            .prefetch_related('items')
            .filter(
                customer__telegram_id=telegram_id,
                status__in=OrderStatus.active_statuses(),
            )
        )
        serializer = OrderSerializer(
            queryset[:ACTIVE_ORDERS_LIMIT],
            many=True,
        )
        return Response(serializer.data)


class ServiceSmokeCleanupAPIView(APIView):
    """Удаляет данные, созданные smoke-скриптом."""

    permission_classes = [HasServiceToken]

    @transaction.atomic
    def post(self, request):
        """Очищает тестовую корзину, заказ и при необходимости клиента."""
        serializer = ServiceSmokeCleanupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        result = {
            'deleted_cart_items': 0,
            'deleted_notifications': 0,
            'deleted_orders': 0,
            'deleted_customer': False,
        }
        customer = Customer.objects.filter(
            telegram_id=payload['telegram_id']
        ).first()
        if not customer:
            return Response(result)

        result['deleted_cart_items'] = customer.cart_items.count()
        if result['deleted_cart_items']:
            customer.cart_items.all().delete()

        order_id = payload.get('order_id')
        if order_id is not None:
            order = customer.orders.filter(pk=order_id).first()
            if order:
                result['deleted_notifications'] += (
                    NotificationEvent.objects.filter(order=order).count()
                )
                order.delete()
                result['deleted_orders'] = 1
            elif Order.objects.filter(pk=order_id).exists():
                raise ValidationError(
                    'Заказ не принадлежит указанному клиенту.'
                )

        if payload['delete_customer']:
            if customer.orders.exists():
                raise ValidationError(
                    'Нельзя удалить клиента, пока у него есть заказы.'
                )
            customer_notifications = NotificationEvent.objects.filter(
                customer=customer,
                order__isnull=True,
            )
            result['deleted_notifications'] += customer_notifications.count()
            customer_notifications.delete()
            customer.delete()
            result['deleted_customer'] = True

        return Response(result)


class ServiceClaimNotificationsAPIView(APIView):
    """Выдает уведомления фоновой очереди."""

    permission_classes = [HasServiceToken]

    @transaction.atomic
    def post(self, request):
        """Забирает уведомления в обработку для воркера."""
        serializer = NotificationClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        limit = serializer.validated_data['limit']
        reclaim_before = (
            timezone.now() - settings.NOTIFICATION_PROCESSING_TIMEOUT
        )
        notifications = list(
            NotificationEvent.objects.select_related(
                'customer',
                'order',
                'order__customer',
            )
            .prefetch_related('order__items')
            .filter(
                Q(status=NotificationEventStatus.PENDING)
                | Q(
                    status=NotificationEventStatus.PROCESSING,
                    updated_at__lt=reclaim_before,
                )
            )
            .order_by('created_at')[:limit]
        )
        identifiers = [notification.pk for notification in notifications]
        if identifiers:
            NotificationEvent.objects.filter(pk__in=identifiers).update(
                status=NotificationEventStatus.PROCESSING
            )
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class ServiceNotificationCompleteAPIView(APIView):
    """Закрывает уведомление как отправленное."""

    permission_classes = [HasServiceToken]

    def post(self, request, notification_id: int):
        """Закрывает уведомление как успешно отправленное."""
        NotificationEvent.objects.filter(pk=notification_id).update(
            status=NotificationEventStatus.COMPLETED,
            processed_at=timezone.now(),
            error_message='',
        )
        return Response({'ok': True})


class ServiceNotificationFailAPIView(APIView):
    """Закрывает уведомление с ошибкой."""

    permission_classes = [HasServiceToken]

    def post(self, request, notification_id: int):
        """Сохраняет ошибку отправки уведомления."""
        serializer = NotificationFailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        NotificationEvent.objects.filter(pk=notification_id).update(
            status=NotificationEventStatus.FAILED,
            processed_at=timezone.now(),
            error_message=serializer.validated_data.get(
                'error_message',
                '',
            ),
        )
        return Response({'ok': True})


class ServiceClaimBroadcastAPIView(APIView):
    """Выдает следующую готовую рассылку."""

    permission_classes = [HasServiceToken]

    @transaction.atomic
    def post(self, request):
        """Забирает ближайшую готовую рассылку."""
        broadcast = (
            Broadcast.objects.filter(status=BroadcastStatus.READY)
            .order_by('created_at')
            .first()
        )
        if not broadcast:
            return Response({})
        broadcast.status = BroadcastStatus.SENDING
        broadcast.save(update_fields=['status', 'updated_at'])
        return Response(BroadcastSerializer(broadcast).data)


class ServiceBroadcastReportAPIView(APIView):
    """Сохраняет отчет по отправке рассылки."""

    permission_classes = [HasServiceToken]

    def post(self, request, broadcast_id: int):
        """Сохраняет статистику завершенной рассылки."""
        broadcast = get_object_or_404(Broadcast, pk=broadcast_id)
        serializer = BroadcastReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        broadcast.delivered_count = payload['delivered_count']
        broadcast.error_count = payload['error_count']
        broadcast.last_error = payload.get('last_error', '')
        broadcast.sent_at = timezone.now()
        broadcast.status = BroadcastStatus.SENT
        broadcast.save(
            update_fields=[
                'delivered_count',
                'error_count',
                'last_error',
                'sent_at',
                'status',
                'updated_at',
            ]
        )
        return Response({'ok': True})
