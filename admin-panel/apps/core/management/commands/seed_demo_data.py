"""Команда заполнения проекта демонстрационными данными."""

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q
from PIL import Image

from apps.botconfig.models import BotSettings
from apps.catalog.models import Category, Product, ProductImage


@dataclass(frozen=True)
class DemoProduct:
    """Описывает один демонстрационный товар."""

    category_path: tuple[str, ...]
    category_slug_path: tuple[str, ...]
    title: str
    slug: str
    description: str
    price: Decimal


DEMO_PRODUCTS: tuple[DemoProduct, ...] = (
    DemoProduct(
        category_path=('Электроника', 'Аудио'),
        category_slug_path=('electronics', 'audio'),
        title='Наушники Nova',
        slug='nova-headphones',
        description=(
            'Беспроводные полноразмерные наушники с активным шумоподавлением.'
        ),
        price=Decimal('12990.00'),
    ),
    DemoProduct(
        category_path=('Электроника', 'Аудио'),
        category_slug_path=('electronics', 'audio'),
        title='Колонка Orbit',
        slug='orbit-speaker',
        description='Портативная колонка со стереопарой и защитой от брызг.',
        price=Decimal('7490.00'),
    ),
    DemoProduct(
        category_path=('Аксессуары', 'Рабочее место'),
        category_slug_path=('accessories', 'desk'),
        title='Лампа Focus',
        slug='focus-lamp',
        description=(
            'Минималистичная настольная лампа с теплым и холодным светом.'
        ),
        price=Decimal('4990.00'),
    ),
    DemoProduct(
        category_path=('Аксессуары', 'Сумки'),
        category_slug_path=('accessories', 'bags'),
        title='Рюкзак Transit',
        slug='transit-backpack',
        description=(
            'Городской рюкзак с отделением для ноутбука '
            'и водоотталкивающей тканью.'
        ),
        price=Decimal('6990.00'),
    ),
    DemoProduct(
        category_path=('Умный дом', 'Комфорт'),
        category_slug_path=('smart-home', 'comfort'),
        title='Диффузор Pulse',
        slug='pulse-diffuser',
        description='Умный аромадиффузор с таймером и тихим ночным режимом.',
        price=Decimal('5890.00'),
    ),
    DemoProduct(
        category_path=('Умный дом', 'Безопасность'),
        category_slug_path=('smart-home', 'security'),
        title='Датчик Home',
        slug='home-sensor',
        description=(
            'Компактный датчик открытия двери, '
            'движения и уровня заряда батареи.'
        ),
        price=Decimal('4590.00'),
    ),
)


PALETTES: tuple[tuple[str, str], ...] = (
    ('#FFB04A', '#F56B2A'),
    ('#29A17A', '#1F6D63'),
    ('#4D78FF', '#1E3A8A'),
    ('#F6D365', '#FDA085'),
    ('#8FD3F4', '#84FAB0'),
    ('#D4A5FF', '#7B4DFF'),
)


class Command(BaseCommand):
    """Заполняет каталог демонстрационными данными."""

    help = (
        'Заполняет демо-каталог локализованными '
        'категориями, товарами и изображениями.'
    )

    def add_arguments(self, parser):
        """Добавляет флаги управления сидированием."""
        parser.add_argument(
            '--replace-images',
            action='store_true',
            help='Пересобрать демо-изображения, даже если они уже существуют.',
        )

    def handle(self, *args, **options):
        """Создает демо-категории, товары и изображения."""
        replace_images = options['replace_images']
        BotSettings.load()
        category_cache: dict[tuple[str, ...], Category] = {}
        created_categories = 0
        created_products = 0
        created_images = 0
        for index, demo_product in enumerate(DEMO_PRODUCTS):
            category = self._ensure_category_path(demo_product, category_cache)
            if category.created:
                created_categories += category.created_count
            product, product_created = self._ensure_product(
                demo_product=demo_product,
                category=category.instance,
                sort_order=index,
            )
            if product_created:
                created_products += 1
            created_images += self._ensure_images(
                product=product,
                palette=PALETTES[index % len(PALETTES)],
                replace=replace_images,
            )
        summary = {
            'categories_cached': len(category_cache),
            'products': Product.objects.count(),
            'product_images': ProductImage.objects.count(),
            'created_categories': created_categories,
            'created_products': created_products,
            'created_images': created_images,
        }
        self.stdout.write(self.style.SUCCESS(f'Демо-данные готовы: {summary}'))

    def _ensure_category_path(
        self,
        demo_product: DemoProduct,
        cache: dict[tuple[str, ...], Category],
    ) -> '_CategoryResult':
        """Создает или находит цепочку категорий."""
        if demo_product.category_path in cache:
            return _CategoryResult(
                instance=cache[demo_product.category_path],
                created=False,
                created_count=0,
            )
        parent = None
        created_count = 0
        for depth in range(1, len(demo_product.category_path) + 1):
            slice_path = demo_product.category_path[:depth]
            if slice_path in cache:
                parent = cache[slice_path]
                continue
            title = slice_path[-1]
            slug = demo_product.category_slug_path[depth - 1]
            category = self._find_category(
                parent=parent,
                title=title,
                slug=slug,
            )
            if category is None:
                category = Category.objects.create(
                    title=title,
                    slug=slug,
                    parent=parent,
                    is_active=True,
                    sort_order=depth,
                )
                created_count += 1
            else:
                updated_fields = []
                if category.title != title:
                    category.title = title
                    updated_fields.append('title')
                if category.slug != slug:
                    category.slug = slug
                    updated_fields.append('slug')
                if not category.is_active:
                    category.is_active = True
                    updated_fields.append('is_active')
                if category.sort_order != depth:
                    category.sort_order = depth
                    updated_fields.append('sort_order')
                if updated_fields:
                    category.save(
                        update_fields=[*updated_fields, 'updated_at']
                    )
            cache[slice_path] = category
            parent = category
        return _CategoryResult(
            instance=cache[demo_product.category_path],
            created=created_count > 0,
            created_count=created_count,
        )

    def _find_category(
        self,
        *,
        parent: Category | None,
        title: str,
        slug: str,
    ) -> Category | None:
        """Ищет категорию по slug или названию."""
        return (
            Category.objects.filter(parent=parent)
            .filter(Q(slug=slug) | Q(title=title))
            .order_by('pk')
            .first()
        )

    def _ensure_product(
        self,
        *,
        demo_product: DemoProduct,
        category: Category,
        sort_order: int,
    ) -> tuple[Product, bool]:
        """Создает или обновляет демо-товар."""
        product = self._find_product(demo_product)
        if product is None:
            product = Product.objects.create(
                category=category,
                title=demo_product.title,
                slug=demo_product.slug,
                description=demo_product.description,
                price=demo_product.price,
                is_active=True,
                sort_order=sort_order,
            )
            return product, True
        updated_fields = []
        if product.category_id != category.pk:
            product.category = category
            updated_fields.append('category')
        if product.title != demo_product.title:
            product.title = demo_product.title
            updated_fields.append('title')
        if product.slug != demo_product.slug:
            product.slug = demo_product.slug
            updated_fields.append('slug')
        if product.description != demo_product.description:
            product.description = demo_product.description
            updated_fields.append('description')
        if product.price != demo_product.price:
            product.price = demo_product.price
            updated_fields.append('price')
        if not product.is_active:
            product.is_active = True
            updated_fields.append('is_active')
        if product.sort_order != sort_order:
            product.sort_order = sort_order
            updated_fields.append('sort_order')
        if updated_fields:
            product.save(update_fields=[*updated_fields, 'updated_at'])
        return product, False

    def _find_product(self, demo_product: DemoProduct) -> Product | None:
        """Ищет демо-товар по slug или названию."""
        return (
            Product.objects.filter(
                Q(slug=demo_product.slug) | Q(title=demo_product.title)
            )
            .order_by('pk')
            .first()
        )

    def _ensure_images(
        self,
        *,
        product: Product,
        palette: tuple[str, str],
        replace: bool,
    ) -> int:
        """Пересоздает или обновляет изображения товара."""
        created_images = 0
        for sort_order in (1, 2):
            image = product.images.filter(sort_order=sort_order).first()
            if image and not replace:
                continue
            image_bytes = self._build_image_bytes(
                color=palette[sort_order - 1],
            )
            filename = f'demo-{product.slug}-{sort_order}.png'
            if image:
                image.image.save(filename, ContentFile(image_bytes), save=True)
                image.alt_text = f'{product.title} {sort_order}'
                image.save(update_fields=['image', 'alt_text', 'updated_at'])
                created_images += 1
                continue
            ProductImage.objects.create(
                product=product,
                alt_text=f'{product.title} {sort_order}',
                sort_order=sort_order,
                image=ContentFile(image_bytes, name=filename),
            )
            created_images += 1
        return created_images

    def _build_image_bytes(
        self,
        *,
        color: str,
    ) -> bytes:
        """Генерирует однотонную картинку-заглушку."""
        image = Image.new('RGB', (1200, 900), color)
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()


@dataclass(frozen=True)
class _CategoryResult:
    """Хранит результат поиска или создания категории."""

    instance: Category
    created: bool
    created_count: int
