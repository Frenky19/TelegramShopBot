# Telegram Shop Bot

Тестовое задание: интернет-магазин в Telegram с Django-админкой, ботом на
Aiogram и WebApp на React.

## Архитектура и обоснование решений

Проект состоит из четырех основных частей:

- `admin-panel` — backend на `Django + DRF`
- `telegram-bot` — бот на `Aiogram 3`
- `webapp` — Telegram WebApp на `React + TypeScript`
- `postgres` — единое хранилище данных

### Как взаимодействуют сервисы

Выбран подход `REST API + единый backend`.

- `admin-panel` владеет бизнес-логикой и данными
- `telegram-bot` работает с backend через service API
- `webapp` работает с backend через публичный и WebApp API
- `postgres` используется только backend-ом, остальные сервисы не ходят в БД напрямую

### Почему выбран именно такой подход

Этот вариант был выбран вместо общей БД между сервисами или shared-пакета с
бизнес-логикой, потому что он:

- уменьшает связность между сервисами
- не дублирует бизнес-логику между ботом и WebApp
- упрощает тестирование и поддержку
- делает backend единым источником корректной информации

### Почему выбран стек Django + Aiogram + React

- `Django` дал админку, ORM и быстрый способ собрать backend API
- `DRF` позволил централизовать валидацию и работу с данными
- `Aiogram 3` хорошо подошел для FSM, callback-кнопок, middleware и inline-режима
- `React` подошел для Telegram WebApp, где нужен более удобный UX каталога и корзины

## Production

Проект развернут в production-окружении.

- WebApp: `https://qrkot.site/`
- Django admin: `https://qrkot.site/admin/` (Логин: admin, Пароль: Admin12345!)
- Telegram бот: `@Frenky19_TestShop_bot` (любой другой бот, привязанный через `TELEGRAM_BOT_TOKEN`)
- Telegram админ-группа: `https://t.me/+L4MoMWOSaO0xZGMy` (любая другая группа, указанная в настройках бота в Django админке. Чтобы управлять заказами из админ группы нужно поставить флаг у пользователя, что он является владельцем бота)

WebApp открывается внутри Telegram через системную кнопку `Menu` и через
inline-кнопку `Открыть WebApp` в каталоге.

## Структура проекта

- `admin-panel` — Django 5 + DRF + PostgreSQL
- `telegram-bot` — Aiogram 3
- `webapp` — React + TypeScript + Vite
- `postgres` — база данных

Backend API и бизнес-логика находятся в `admin-panel`. Бот и WebApp работают
с backend через HTTP API.

Основные директории:

- `admin-panel/apps/catalog` — категории, товары, изображения
- `admin-panel/apps/customers` — клиенты и корзина
- `admin-panel/apps/orders` — заказы, позиции заказов, уведомления
- `admin-panel/apps/marketing` — FAQ и рассылки
- `admin-panel/apps/botconfig` — настройки бота и обязательные каналы
- `admin-panel/apps/api` — публичный и сервисный API
- `telegram-bot/app/routers` — роутеры бота
- `telegram-bot/app/middlewares.py` — middleware бота
- `webapp/src` — frontend WebApp
- `scripts` — вспомогательные скрипты, включая smoke-проверку
- `deploy` — production-конфиги для reverse proxy и серверного запуска

## Реализовано

- регистрация пользователя через контакт Telegram
- каталог, карточка товара, корзина и оформление заказа
- deep link вида `?start=product_<id>`
- кнопка `Я оплатил(а)` и смена статусов заказа
- админ-группа с кнопкой `Активные заказы`
- клиентская кнопка `Мои заказы`
- FAQ через `inline_query`
- рассылки из админки
- Telegram WebApp с общей корзиной и checkout

## Сценарий

### 1. Бот

1. Открыть бота и отправить `/start`.
2. Передать контакт.
3. Открыть каталог.
4. Перейти в карточку товара.
5. Добавить товар в корзину.
6. Оформить заказ: указать ФИО и адрес.
7. Нажать `Я оплатил(а)`.

Ожидаемый результат:

- заказ создается успешно
- клиент получает уведомления о смене статуса
- в админ-группу приходит сообщение о новом заказе

### 2. Админ-группа

1. Нажать `Активные заказы`.
2. Открыть созданный заказ.
3. Перевести его по статусам:
   - `Оплачен`
   - `В обработке`
   - `Отправлен`
   - `Завершен`

Ожидаемый результат:

- статус меняется и в Telegram, и в админке
- клиент получает уведомление после каждой смены статуса

### 3. Django admin

В админке доступны:

- категории и товары с несколькими изображениями
- клиенты
- заказы
- FAQ
- рассылки
- настройки бота

Дополнительно можно проверить:

- экспорт оплаченных заказов в Excel
- создание FAQ
- создание рассылки с изображением `png`, `jpg` или `jpeg`

### 4. WebApp

1. Открыть WebApp внутри Telegram через `Menu` или `Открыть WebApp`.
2. Проверить каталог, поиск и фильтрацию по категориям.
3. Добавить товар в корзину.
4. Открыть корзину.
5. Перейти к оформлению заказа.

Ожидаемый результат:

- WebApp использует тот же каталог, что и бот
- корзина общая с ботом
- оформление заказа работает через backend API

## Локальный запуск

Если нужно поднять проект локально:

1. Скопировать `.env.example` в `.env`.
2. Заполнить минимум:
   - `TELEGRAM_BOT_TOKEN`
   - `INTERNAL_SERVICE_TOKEN`
3. Поднять контейнеры:

```bash
docker compose up -d --build
```

4. Заполнить демо-каталог:

```bash
docker compose exec admin-panel python manage.py seed_demo_data
```

Точки входа локально:

- Django admin: `http://localhost:8000/admin/`
- WebApp в браузере: `http://localhost:5173/`

Если используются значения из `.env.example`, суперпользователь создается
автоматически:

- логин: `admin`
- пароль: `Admin12345!`

## Переменные окружения

Все основные переменные перечислены в `.env.example`

Ключевые группы:

### База данных

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`

### Django

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `PUBLIC_BASE_URL`

### Суперпользователь

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`

### Telegram и внутренние сервисы

- `TELEGRAM_BOT_TOKEN`
- `INTERNAL_SERVICE_TOKEN`
- `BACKEND_URL`
- `MEDIA_BASE_URL`

### Фоновые задачи бота

- `SETTINGS_CACHE_TTL`
- `NOTIFICATION_POLL_INTERVAL`
- `BROADCAST_POLL_INTERVAL`

### Frontend / WebApp

- `VITE_PROXY_TARGET`
- `VITE_DEV_INIT_DATA`

### Логи и серверные bind-порты

- `LOGS_DIR`
- `ADMIN_PANEL_BIND_PORT`
- `WEBAPP_BIND_PORT`
- `GATEWAY_BIND_PORT`

## Production-деплой

Для серверного деплоя в репозитории есть:

- `docker-compose.server.yml`
- `webapp/Dockerfile.prod`
- `deploy/gateway/nginx.conf`
- `deploy/nginx/qrkot.site.docker-proxy.conf.template`

Стенд рассчитан на reverse proxy перед контейнерами и домен `qrkot.site`.

## Автоматическая smoke-проверка

Для быстрой автоматической проверки:

```bash
python scripts/smoke_order.py --base-url https://qrkot.site --service-token <INTERNAL_SERVICE_TOKEN>
```

Скрипт:

- берет первый товар из каталога
- создает тестового клиента
- оформляет заказ
- переводит его до `completed`
- закрывает уведомления
- автоматически удаляет тестовые данные после завершения

Если тестовые данные нужно оставить:

```bash
python scripts/smoke_order.py --base-url https://qrkot.site --service-token <INTERNAL_SERVICE_TOKEN> --no-cleanup
```

## Полезные команды

Заполнить демо-данные:

```bash
docker compose exec admin-panel python manage.py seed_demo_data
```

Пересоздать демо-изображения:

```bash
docker compose exec admin-panel python manage.py seed_demo_data --replace-images
```

Проверить backend:

```bash
python admin-panel/manage.py check
```

Запустить тесты:

```bash
pytest admin-panel
```

Запустить линтер:

```bash
ruff check .
```
