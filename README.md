# CRM Logistics

CRM Logistics — Django‑проєкт для управління доставкою: клієнти, курʼєри, замовлення, платежі, маршрути, аналітика та сповіщення.

**Можливості**
- Облік клієнтів і курʼєрів, статуси доступності та типи транспорту.
- Управління замовленнями з пріоритетами, статусами, примітками та автоматичним розрахунком вартості.
- Платежі з різними методами і статусами, швидке створення оплат.
- Логістична панель: оптимізація маршрутів, трекінг курʼєрів, аналітика доставок, авто‑призначення.
- GPS‑історія курʼєрів, зони доставки, облік трафіку.
- Email‑сповіщення для клієнтів, менеджерів і курʼєрів.
- API‑ендпоїнти для геокодування, локацій курʼєрів, вебхуків платежів і сапорт‑чату.
- Локальний AI‑чат підтримки через Ollama (опційно).

**Стек**
- Django 5, Django REST Framework
- SQLite за замовчуванням
- requests, geopy, folium

**Швидкий старт**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Після запуску відкрийте `http://127.0.0.1:8000/` і `http://127.0.0.1:8000/admin/`.

**Конфігурація (ENV)**
- `DJANGO_SECRET_KEY` — секретний ключ Django.
- `DJANGO_DEBUG` — режим дебагу, за замовчуванням `True`.
- `DJANGO_ALLOWED_HOSTS` — список хостів через кому.
- `OPENROUTE_API_KEY` — ключ OpenRouteService для маршрутизації (опційно).
- `EXTERNAL_ROUTING_ENABLED` — вмикає зовнішню маршрутизацію, за замовчуванням `true`.
- `COURIER_LOCATION_API_KEY` — ключ для API локацій курʼєрів (опційно).
- `PAYMENT_WEBHOOK_SECRET` — секрет для webhook‑ендпоїнта платежів (опційно).
- `OLLAMA_URL` — URL локального Ollama (за замовчуванням `http://localhost:11434`).
- `OLLAMA_MODEL` — модель Ollama (за замовчуванням `gemma3:4b`).
- `EMAIL_HOST_USER` і `EMAIL_HOST_PASSWORD` — SMTP‑облікові дані для продакшн‑відправки.

У режимі `DEBUG` email відправляються в консоль, а API‑ключі для публічних ендпоїнтів можуть бути необовʼязковими.

**Демо‑дані та корисні команди**
```bash
python manage.py populate_demo_data
python manage.py populate_logistics_data
python manage.py create_diploma_demo --orders 15

python manage.py test
python manage.py test_email_notifications
python manage.py test_real_routes
```
`populate_demo_data` створює `admin/admin123` і `manager/manager123` для демо.

**API ендпоїнти (скорочено)**
- `POST /api/courier-location/` — оновлення координат курʼєра.
- `POST /api/geocode/` — геокодування адреси.
- `POST /api/create-client/` — створення клієнта.
- `POST /api/payment-webhook/` — webhook платежів.
- `POST /api/support-chat/` — чат підтримки (Ollama).

**Структура проєкту**
- `crm/` — основний застосунок (моделі, логіка, шаблони, статика).
- `crm_project/` — налаштування Django.
- `db.sqlite3` — локальна база даних.
- `logs/crm.log` — файл логів.

Якщо хочеш, можу додати розділ про деплой або деталізувати API контракт.
