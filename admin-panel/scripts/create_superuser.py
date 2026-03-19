"""Скрипт создания администратора по переменным окружения."""

import os
import sys
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402


def main() -> None:
    """Запускает основной сценарий приложения."""
    username = os.getenv('DJANGO_SUPERUSER_USERNAME', '').strip()
    email = os.getenv('DJANGO_SUPERUSER_EMAIL', '').strip()
    password = os.getenv('DJANGO_SUPERUSER_PASSWORD', '').strip()
    if not username or not password:
        print('Skipping superuser bootstrap: credentials are not configured.')
        return
    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'is_staff': True,
            'is_superuser': True,
        },
    )
    updated = False
    if email and user.email != email:
        user.email = email
        updated = True
    if not user.is_staff:
        user.is_staff = True
        updated = True
    if not user.is_superuser:
        user.is_superuser = True
        updated = True
    if created or not user.check_password(password):
        user.set_password(password)
        updated = True
    if updated:
        user.save()
    action = 'created' if created else 'updated'
    print(f'Superuser {action}: {username}')


if __name__ == '__main__':
    main()
