import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")  # Required; validated at startup in create_app
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 1209600  # 14 days in seconds
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'investmap.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = str(BASE_DIR / "app" / "static" / "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    MAP_CENTER = (43.1155, 131.8855)  # Vladivostok
    MAP_ZOOM = 11

    # --- Email (dev по умолчанию пишет в лог, без реального SMTP) ---
    MAIL_ENABLED = os.environ.get("MAIL_ENABLED", "false").lower() in ("1", "true", "yes")
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "no-reply@investmap.ru")
    MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "InvestMap")
    DISTRICTS = [
        "Владивосток",
        "Находка",
        "Уссурийск",
        "Артём",
        "Спасск-Дальний",
        "Дальнегорск",
        "Партизанск",
        "Лесозаводск",
        "Надеждинский район",
        "Лучегорск",
    ]
    PROJECT_TYPES = [
        ("infrastructure", "Инфраструктура"),
        ("business", "Бизнес"),
        ("ecology", "Экология"),
        ("social", "Социальный"),
        ("transport", "Транспорт"),
        ("education", "Образование"),
        ("culture", "Культура"),
    ]
    PROJECT_STATUSES = [
        ("planned", "Запланирован"),
        ("in_progress", "Реализуется"),
        ("completed", "Завершён"),
        ("paused", "Приостановлен"),
    ]
