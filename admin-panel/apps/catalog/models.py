"""Модели приложения каталога."""

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimestampedModel


class Category(TimestampedModel):
    """Хранит раздел каталога."""

    title = models.CharField('Название', max_length=120)
    slug = models.SlugField('Slug', max_length=140, unique=True, blank=True)
    parent = models.ForeignKey(
        'self',
        verbose_name='Родительская категория',
        related_name='children',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    is_active = models.BooleanField('Активна', default=True)
    sort_order = models.PositiveIntegerField('Порядок сортировки', default=0)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('sort_order', 'title')
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        """Возвращает название категории."""
        return self.title

    def save(self, *args, **kwargs):
        """Автоматически заполняет slug перед сохранением."""
        if not self.slug:
            base_slug = slugify(self.title) or 'category'
            slug = base_slug
            index = 1
            while (
                Category.objects.exclude(pk=self.pk).filter(slug=slug).exists()
            ):
                index += 1
                slug = f'{base_slug}-{index}'
            self.slug = slug
        super().save(*args, **kwargs)


class Product(TimestampedModel):
    """Хранит карточку товара."""

    category = models.ForeignKey(
        Category,
        verbose_name='Категория',
        related_name='products',
        on_delete=models.PROTECT,
    )
    title = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', max_length=220, unique=True, blank=True)
    description = models.TextField('Описание', blank=True)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    is_active = models.BooleanField('Активен', default=True)
    sort_order = models.PositiveIntegerField('Порядок сортировки', default=0)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('sort_order', 'title')
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        """Возвращает название товара."""
        return self.title

    def save(self, *args, **kwargs):
        """Автоматически заполняет slug перед сохранением."""
        if not self.slug:
            base_slug = slugify(self.title) or 'product'
            slug = base_slug
            index = 1
            while (
                Product.objects.exclude(pk=self.pk).filter(slug=slug).exists()
            ):
                index += 1
                slug = f'{base_slug}-{index}'
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def primary_image(self):
        """Возвращает первое изображение товара."""
        return self.images.order_by('sort_order', 'pk').first()


class ProductImage(TimestampedModel):
    """Хранит дополнительное изображение товара."""

    product = models.ForeignKey(
        Product,
        verbose_name='Товар',
        related_name='images',
        on_delete=models.CASCADE,
    )
    image = models.ImageField('Изображение', upload_to='products/%Y/%m/%d')
    alt_text = models.CharField('Alt text', max_length=255, blank=True)
    sort_order = models.PositiveIntegerField('Порядок сортировки', default=0)

    class Meta:
        """Задает параметры отображения модели."""

        ordering = ('sort_order', 'pk')
        verbose_name = 'Изображение товара'
        verbose_name_plural = 'Изображения товаров'

    def __str__(self):
        """Возвращает подпись изображения для админки."""
        return f'{self.product.title} #{self.pk}'
