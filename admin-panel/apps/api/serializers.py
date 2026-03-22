"""Сериализаторы публичного и сервисного API."""

from rest_framework import serializers

from apps.api.constants import (
    MAX_CART_ITEM_QUANTITY,
    MAX_CHECKOUT_ADDRESS_LENGTH,
    MAX_NOTIFICATION_ERROR_LENGTH,
    NOTIFICATION_CLAIM_DEFAULT_LIMIT,
    NOTIFICATION_CLAIM_MAX_LIMIT,
    NOTIFICATION_CLAIM_MIN_LIMIT,
)
from apps.botconfig.models import BotSettings, RequiredChannel
from apps.catalog.models import Category, Product, ProductImage
from apps.customers.models import CartItem, Customer
from apps.marketing.models import FAQ, Broadcast
from apps.orders.models import NotificationEvent, Order, OrderItem, OrderStatus


class ProductImageSerializer(serializers.ModelSerializer):
    """Сериализует изображение товара для API."""

    image = serializers.SerializerMethodField()

    class Meta:
        """Задает модель и поля сериализатора."""

        model = ProductImage
        fields = ('id', 'image', 'alt_text', 'sort_order')

    def get_image(self, obj):
        """Возвращает абсолютный путь к изображению."""
        return obj.image.url if obj.image else ''


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Сериализует дерево активных категорий каталога."""

    children = serializers.SerializerMethodField()

    class Meta:
        """Задает модель и поля сериализатора."""

        model = Category
        fields = ('id', 'title', 'slug', 'parent', 'children')

    def get_children(self, obj):
        """Сериализует дочерние активные категории."""
        children_map = self.context.get('category_children_map')
        if children_map is not None:
            return CategoryTreeSerializer(
                children_map.get(obj.id, []),
                many=True,
                context=self.context,
            ).data

        queryset = obj.children.filter(is_active=True).order_by(
            'sort_order', 'title'
        )
        return CategoryTreeSerializer(
            queryset, many=True, context=self.context
        ).data


class ProductListSerializer(serializers.ModelSerializer):
    """Сериализует товар для списка каталога."""

    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        """Задает модель и поля сериализатора."""

        model = Product
        fields = (
            'id',
            'category',
            'title',
            'slug',
            'description',
            'price',
            'images',
        )


class ProductDetailSerializer(ProductListSerializer):
    """Сериализует полную карточку товара."""

    class Meta(ProductListSerializer.Meta):
        """Задает модель и поля сериализатора."""

        fields = ProductListSerializer.Meta.fields


class CustomerSerializer(serializers.ModelSerializer):
    """Сериализует профиль клиента."""

    class Meta:
        """Задает модель и поля сериализатора."""

        model = Customer
        fields = (
            'id',
            'telegram_id',
            'username',
            'first_name',
            'last_name',
            'phone',
            'language_code',
            'is_bot_admin',
        )


class CartItemSerializer(serializers.ModelSerializer):
    """Сериализует позицию корзины с товаром."""

    product = ProductListSerializer(read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        """Задает модель и поля сериализатора."""

        model = CartItem
        fields = ('id', 'product', 'quantity', 'line_total')

    def get_line_total(self, obj):
        """Возвращает сумму позиции корзины."""
        return obj.line_total


class CartSerializer(serializers.Serializer):
    """Сериализует корзину и итоговую сумму."""

    items = CartItemSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализует позицию заказа."""

    line_total = serializers.SerializerMethodField()

    class Meta:
        """Задает модель и поля сериализатора."""

        model = OrderItem
        fields = (
            'id',
            'product',
            'product_title',
            'product_price',
            'quantity',
            'line_total',
        )

    def get_line_total(self, obj):
        """Возвращает сумму позиции заказа."""
        return obj.line_total


class OrderSerializer(serializers.ModelSerializer):
    """Сериализует заказ вместе с клиентом и позициями."""

    items = OrderItemSerializer(many=True, read_only=True)
    customer = CustomerSerializer(read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        """Задает модель и поля сериализатора."""

        model = Order
        fields = (
            'id',
            'customer',
            'status',
            'status_display',
            'full_name',
            'phone',
            'address',
            'total_amount',
            'payment_stub_id',
            'created_at',
            'items',
        )


class FAQSerializer(serializers.ModelSerializer):
    """Сериализует запись блока вопросов и ответов."""

    class Meta:
        """Задает модель и поля сериализатора."""

        model = FAQ
        fields = ('id', 'question', 'answer', 'is_popular')


class RequiredChannelSerializer(serializers.ModelSerializer):
    """Сериализует обязательный канал подписки."""

    subscription_url = serializers.CharField(read_only=True)

    class Meta:
        """Задает модель и поля сериализатора."""

        model = RequiredChannel
        fields = ('id', 'title', 'chat_id', 'username', 'subscription_url')


class BotSettingsSerializer(serializers.ModelSerializer):
    """Сериализует настройки бота для клиентов и сервиса."""

    required_channels = serializers.SerializerMethodField()

    class Meta:
        """Задает модель и поля сериализатора."""

        model = BotSettings
        fields = (
            'admin_chat_id',
            'catalog_webapp_url',
            'help_text',
            'subscription_message',
            'required_channels',
        )

    def get_required_channels(self, obj):
        """Возвращает активные каналы обязательной подписки."""
        channels = RequiredChannel.objects.filter(is_active=True).order_by(
            'sort_order', 'title'
        )
        return RequiredChannelSerializer(channels, many=True).data


class NotificationSerializer(serializers.ModelSerializer):
    """Сериализует событие очереди уведомлений."""

    order = OrderSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)

    class Meta:
        """Задает модель и поля сериализатора."""

        model = NotificationEvent
        fields = ('id', 'event_type', 'status', 'payload', 'order', 'customer')


class BroadcastSerializer(serializers.ModelSerializer):
    """Сериализует рассылку и счетчики отправки."""

    image = serializers.SerializerMethodField()
    recipients = serializers.SerializerMethodField()

    class Meta:
        """Задает модель и поля сериализатора."""

        model = Broadcast
        fields = (
            'id',
            'title',
            'text',
            'image',
            'status',
            'delivered_count',
            'error_count',
            'recipients',
        )

    def get_image(self, obj):
        """Возвращает ссылку на картинку рассылки."""
        return obj.image.url if obj.image else ''

    def get_recipients(self, obj):
        """Возвращает список Telegram ID получателей."""
        return list(Customer.objects.values_list('telegram_id', flat=True))


class TelegramCustomerReferenceSerializer(serializers.Serializer):
    """Проверяет ссылку на клиента по Telegram ID."""

    telegram_id = serializers.IntegerField(min_value=1)


class ServiceSyncCustomerSerializer(TelegramCustomerReferenceSerializer):
    """Проверяет данные синхронизации клиента."""

    username = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Customer._meta.get_field('username').max_length,
    )
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Customer._meta.get_field('first_name').max_length,
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Customer._meta.get_field('last_name').max_length,
    )
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Customer._meta.get_field('phone').max_length,
    )
    language_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Customer._meta.get_field('language_code').max_length,
    )


class CheckoutInputSerializer(serializers.Serializer):
    """Проверяет данные оформления заказа."""

    full_name = serializers.CharField(
        max_length=Order._meta.get_field('full_name').max_length,
        trim_whitespace=True,
        allow_blank=True,
    )
    address = serializers.CharField(
        max_length=MAX_CHECKOUT_ADDRESS_LENGTH,
        trim_whitespace=True,
        allow_blank=True,
    )

    def validate_full_name(self, value: str) -> str:
        """Нормализует и проверяет ФИО получателя."""
        normalized = ' '.join(value.split())
        if not normalized:
            raise serializers.ValidationError('Введите ФИО.')
        return normalized

    def validate_address(self, value: str) -> str:
        """Очищает и проверяет адрес доставки."""
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError('Введите адрес доставки.')
        return normalized


class ServiceCheckoutSerializer(
    TelegramCustomerReferenceSerializer, CheckoutInputSerializer
):
    """Проверяет оформление заказа через сервисный API."""

    pass


class WebAppCartItemCreateSerializer(serializers.Serializer):
    """Проверяет добавление товара в корзину WebApp."""

    product_id = serializers.IntegerField(min_value=1)
    delta = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
        max_value=MAX_CART_ITEM_QUANTITY,
    )


class WebAppCartItemUpdateSerializer(serializers.Serializer):
    """Проверяет изменение количества в корзине WebApp."""

    quantity = serializers.IntegerField(
        min_value=0, max_value=MAX_CART_ITEM_QUANTITY
    )


class ServiceCartItemSerializer(TelegramCustomerReferenceSerializer):
    """Проверяет операции с корзиной через сервисный API."""

    product_id = serializers.IntegerField(min_value=1)
    mode = serializers.ChoiceField(
        choices=('increment', 'set'), default='increment'
    )
    delta = serializers.IntegerField(
        required=False,
        default=1,
        min_value=-MAX_CART_ITEM_QUANTITY,
        max_value=MAX_CART_ITEM_QUANTITY,
    )
    quantity = serializers.IntegerField(
        required=False, min_value=0, max_value=MAX_CART_ITEM_QUANTITY
    )

    def validate(self, attrs):
        """Проверяет режим операции и связанные поля."""
        mode = attrs['mode']
        quantity = attrs.get('quantity')
        delta = attrs.get('delta')

        if mode == 'set':
            if quantity is None:
                raise serializers.ValidationError(
                    {'quantity': 'Передайте количество для режима set.'}
                )
            return attrs

        if delta == 0:
            raise serializers.ValidationError(
                {'delta': 'Изменение количества не может быть равно 0.'}
            )
        return attrs


class ServiceOrderStatusSerializer(serializers.Serializer):
    """Проверяет новый статус заказа."""

    status = serializers.ChoiceField(choices=OrderStatus.values)


class ServiceSmokeCleanupSerializer(TelegramCustomerReferenceSerializer):
    """Проверяет параметры очистки после smoke-прогона."""

    order_id = serializers.IntegerField(required=False, min_value=1)
    delete_customer = serializers.BooleanField(required=False, default=False)


class NotificationClaimSerializer(serializers.Serializer):
    """Проверяет параметры выборки уведомлений."""

    limit = serializers.IntegerField(
        required=False,
        default=NOTIFICATION_CLAIM_DEFAULT_LIMIT,
        min_value=NOTIFICATION_CLAIM_MIN_LIMIT,
        max_value=NOTIFICATION_CLAIM_MAX_LIMIT,
    )


class NotificationFailSerializer(serializers.Serializer):
    """Проверяет текст ошибки уведомления."""

    error_message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MAX_NOTIFICATION_ERROR_LENGTH,
    )


class BroadcastReportSerializer(serializers.Serializer):
    """Проверяет отчет по отправленной рассылке."""

    delivered_count = serializers.IntegerField(
        required=False, default=0, min_value=0
    )
    error_count = serializers.IntegerField(
        required=False, default=0, min_value=0
    )
    last_error = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MAX_NOTIFICATION_ERROR_LENGTH,
    )
