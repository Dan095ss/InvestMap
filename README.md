# InvestMap — Инвестиционная карта Приморского края

Интерактивный веб-портал инвестиционных проектов и гражданских инициатив  
Приморского края. Четыре города: Владивосток, Артём, Уссурийск, Находка.  
40 реальных проектов · 40 инициатив · интерактивная карта · краудфандинг · личный кабинет

---

## Быстрый старт (Windows)

### Вариант 1 — двойной клик

Запустите **`start.bat`**.  
Всё произойдёт автоматически: создаётся окружение, ставятся зависимости,
наполняется база данных, запускается сервер.

### Вариант 2 — PowerShell

```powershell
.\start.ps1
```

После запуска откройте браузер: **http://127.0.0.1:5000**

---

## Ручная установка

### Требования

- Python 3.10 или новее ([скачать](https://python.org/downloads))
- pip (входит в Python)

### Шаги

```bash
# 1. Создайте и активируйте виртуальное окружение
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# 2. Установите зависимости
pip install -r requirements.txt

# 3. Создайте .env с ключом безопасности
python -c "import secrets; open('.env','w').write('SECRET_KEY='+secrets.token_hex(32)+'\n')"

# 4. Загрузите .env и наполните базу данных
# Windows (cmd):
for /f "tokens=1,2 delims==" %A in (.env) do set %A=%B
# PowerShell:
$env:SECRET_KEY = (Get-Content .env | Select-String "SECRET_KEY").ToString().Split("=",2)[1]

python seed.py

# 5. Запустите сервер
python run.py
```

---

## Тестовые аккаунты

| Email | Пароль | Роль |
|-------|--------|------|
| admin@investmap.ru | admin123 | Администратор |
| moderator@investmap.ru | moderator123 | Модератор |
| user@investmap.ru | user1234 | Пользователь |
| investor@investmap.ru | invest1234 | Инвестор (юрлицо) |

---

## Пересоздание базы данных

Если нужно загрузить данные заново:

```bash
del instance\investmap.db      # Windows
python seed.py
```

---

## Запуск тестов

```bash
python -m pytest tests/ -v
```

---

## Структура проекта

```
InvestMap/
├── app/
│   ├── blueprints/       # Маршруты: auth, projects, initiatives, cabinet, api, admin
│   ├── models.py         # Модели SQLAlchemy
│   ├── static/           # CSS, JS, uploads (фото проектов и инициатив)
│   └── templates/        # Jinja2-шаблоны
├── instance/             # investmap.db — создаётся автоматически
├── tests/                # Pytest-тесты (76 тестов)
├── Наполнение продукта/  # Исходный Excel и фотографии
├── seed.py               # Наполнение БД из Excel
├── run.py                # Точка входа Flask
├── config.py             # Конфигурация (SECRET_KEY, БД, справочники)
├── requirements.txt      # Зависимости Python
├── start.bat             # Запускатор для Windows (cmd)
└── start.ps1             # Запускатор для PowerShell
```

---

## Стек

- **Flask 3** + Blueprints
- **Flask-SQLAlchemy** + **SQLite** (переключается на PostgreSQL через `DATABASE_URL`)
- **Flask-Login** — авторизация
- **Leaflet + OpenStreetMap** — карта (без API-ключей)
- **Jinja2** + собственный CSS (без Bootstrap/Tailwind)
- **openpyxl** — чтение исходных данных из Excel при seed
