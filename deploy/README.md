# Деплой на сервер с host nginx

Этот вариант подходит для сервера, где `nginx` уже установлен и обслуживает
несколько проектов. Контейнеры публикуются только на `127.0.0.1`, а внешний
доступ идет через отдельный `server_name`.

## Целевая схема

- домен: `qrkot.site`
- backend: `127.0.0.1:18000`
- WebApp: `127.0.0.1:18080`
- bot: без внешнего порта

## 1. DNS

Создайте записи:

- `A` -> `195.133.81.189`
- `AAAA` -> `2a03:6f02::1:43c3`

## 2. Размещение проекта

Не размещайте проект в `/root`, если `nginx` должен читать `static` и `media`
через `alias`. Рекомендуемый путь:

```bash
/opt/telegram-shop-bot
```

Пример:

```bash
mkdir -p /opt/telegram-shop-bot
cd /opt/telegram-shop-bot
git clone <repo-url> .
```

## 3. Переменные окружения

Создайте `.env` на сервере и задайте минимум:

```env
POSTGRES_DB=telegram_shop
POSTGRES_USER=postgres
POSTGRES_PASSWORD=strong-password
DATABASE_URL=postgresql://postgres:strong-password@postgres:5432/telegram_shop

DJANGO_SECRET_KEY=strong-secret-key
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=qrkot.site,www.qrkot.site,localhost,127.0.0.1,admin-panel
DJANGO_CSRF_TRUSTED_ORIGINS=https://qrkot.site,https://www.qrkot.site
DJANGO_USE_X_FORWARDED_HOST=1
DJANGO_TRUST_X_FORWARDED_PROTO=1
DJANGO_SESSION_COOKIE_SECURE=1
DJANGO_CSRF_COOKIE_SECURE=1
PUBLIC_BASE_URL=https://qrkot.site

DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=Admin12345!

TELEGRAM_BOT_TOKEN=<telegram-bot-token>
INTERNAL_SERVICE_TOKEN=<internal-service-token>
BACKEND_URL=http://admin-panel:8000
MEDIA_BASE_URL=http://admin-panel:8000

ADMIN_PANEL_BIND_PORT=18000
WEBAPP_BIND_PORT=18080
```

## 4. Запуск контейнеров

Из корня проекта:

```bash
docker compose -f docker-compose.server.yml up -d --build
```

Проверка:

```bash
docker compose -f docker-compose.server.yml ps
```

## 5. Настройка nginx

1. Скопируйте шаблон:

   ```bash
   cp deploy/nginx/qrkot.site.conf.template /etc/nginx/sites-available/qrkot.site
   ```

2. Замените `<PROJECT_ROOT>` на реальный путь, например:

   ```text
   /opt/telegram-shop-bot
   ```

3. Включите сайт:

   ```bash
   ln -s /etc/nginx/sites-available/qrkot.site /etc/nginx/sites-enabled/qrkot.site
   nginx -t
   systemctl reload nginx
   ```

## 6. SSL

После того как сайт доступен по HTTP, выпустите сертификат:

```bash
certbot --nginx -d qrkot.site -d www.qrkot.site
```

## 7. Финальная настройка проекта

1. Откройте `https://qrkot.site/admin/`.
2. Войдите под суперпользователем.
3. Выполните:

   - `seed_demo_data`, если каталог еще пуст
   - настройку `admin_chat_id`
   - заполнение `catalog_webapp_url=https://qrkot.site/`

После этого кнопка WebApp в Telegram будет открывать встроенное приложение.
