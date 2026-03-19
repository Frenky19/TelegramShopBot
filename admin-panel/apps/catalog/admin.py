"""Настройки Django admin для приложения каталога."""

from django.contrib import admin

from apps.catalog.models import Category, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    """Показывает изображения внутри карточки товара."""

    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Настраивает список и форму категорий."""

    list_display = ('title', 'parent', 'is_active', 'sort_order')
    list_filter = ('is_active', 'parent')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Настраивает список и форму товаров."""

    list_display = ('title', 'category', 'price', 'is_active', 'sort_order')
    list_filter = ('is_active', 'category')
    search_fields = ('title', 'description', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ProductImageInline]
