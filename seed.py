"""Seed script — loads real data from Наполнение продукта/Сайт_Наполнение.xlsx.

Run: python seed.py
Drops all tables, recreates, and loads 40 projects + 40 initiatives.
"""
import re
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl
from slugify import slugify

from app import create_app
from app.extensions import db
from app.models import (
    User, Project, Job, Comment, Initiative,
    Donation, InitiativeVote, Subscription, Notification,
)

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "Наполнение продукта" / "Сайт_Наполнение.xlsx"
IMAGES_DST = BASE_DIR / "app" / "static" / "uploads"

DISTRICT_MAP = {"В": "Владивосток", "А": "Артём", "У": "Уссурийск", "Н": "Находка"}

STATUS_MAP = {
    "Реализуется": "in_progress",
    "Запланирован": "planned",
    "Реализован": "completed",
    "Приостановлен": "paused",
}

INITIATIVE_STATUS_MAP = {"Собрано": "funded", "Не собрано": "active"}

TYPE_MAP = {
    "Культура": "culture",
    "Социальный": "social",
    "Инфраструктура": "infrastructure",
    "Бизнес": "business",
    "Транспорт": "transport",
    "Экология": "ecology",
    "Образование": "education",
}

CHAT_TEMPLATES = {
    "transport": [
        ("Когда планируется открытие для движения?", False),
        ("Открытие запланировано по утверждённому графику. Следите за обновлениями на портале.", True),
    ],
    "social": [
        ("Ждём открытия! Нашему району очень нужен этот объект.", False),
        ("Благодарим за поддержку! Работы ведутся по плану.", True),
    ],
    "ecology": [
        ("Отличная инициатива! Когда можно будет посетить объект?", False),
        ("Объект будет открыт для посещений после завершения всех работ.", True),
    ],
    "culture": [
        ("Очень ждём открытие! Такой объект давно нужен городу.", False),
        ("Спасибо за интерес! Следите за анонсами открытия на портале.", True),
    ],
    "business": [
        ("Есть ли возможность для малого бизнеса участвовать в проекте?", False),
        ("Для получения информации свяжитесь с администрацией проекта.", True),
    ],
    "infrastructure": [
        ("Как этот объект скажется на развитии района?", False),
        ("Проект направлен на повышение качества жизни горожан и развитие инфраструктуры.", True),
    ],
    "education": [
        ("Когда планируется запуск? Уже открыта запись?", False),
        ("Подробная информация о записи появится ближе к открытию объекта.", True),
    ],
}
_CHAT_DEFAULT = CHAT_TEMPLATES["social"]


def _parse_coords(text: str):
    m = re.search(r'(\d{2,3}\.\d+),\s*(\d{2,3}\.\d+)', str(text or ""))
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _parse_address(text: str) -> str:
    return re.sub(r'\s*\d{2,3}\.\d+,\s*\d{2,3}\.\d+', '', str(text or "")).strip().rstrip(',').strip()


def _safe_date(s: str):
    s = s.strip()
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        try:
            parts = s.split('.')
            y, m = int(parts[2]), int(parts[1])
            last_day = calendar.monthrange(y, m)[1]
            return date(y, m, last_day)
        except Exception:
            return None


def _parse_dates(text: str):
    t = re.sub(r'\s+', '', str(text or ""))
    m_end = re.search(r'[Дд]о(\d{2}\.\d{2}\.\d{4})', t)
    if m_end:
        return None, _safe_date(m_end.group(1))
    m_range = re.search(r'(\d{2}\.\d{2}\.\d{4})-(\d{2}\.\d{2}\.\d{4})', t)
    if m_range:
        return _safe_date(m_range.group(1)), _safe_date(m_range.group(2))
    return None, None


def _parse_jobs(text: str, project_id_hint: int = 0) -> list:
    if not text or str(text).strip().startswith('/') or str(text).strip() == '':
        return []
    jobs = []
    parts = re.split(r'\n?\d+\.\s+', str(text))
    parts = [p.strip() for p in parts if p.strip() and not p.strip().startswith('/')]
    for i, part in enumerate(parts):
        sal = re.search(r'([\d\s]+)\s*₽\s*[—\-]\s*([\d\s]+)\s*₽', part)
        if sal:
            salary_min = int(re.sub(r'\s', '', sal.group(1)))
            salary_max = int(re.sub(r'\s', '', sal.group(2)))
            idx = part.find(sal.group(0))
            title = part[:idx].strip().rstrip('\n').strip()
            req = part[idx + len(sal.group(0)):].strip().lstrip(',').strip().rstrip('.')
        else:
            title = part.split('\n')[0].strip()
            salary_min = salary_max = None
            req = '\n'.join(part.split('\n')[1:]).strip()
        if not title:
            continue
        n = (project_id_hint * 7 + i * 13) % 900 + 100
        contact = f"hr@investmap-primorye.ru | +7 (423) {n // 10:02d}-{n % 10}{(n * 3) % 10}-{(n * 7) % 100:02d}"
        jobs.append({
            "title": title,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "requirements": req or "Требования уточняются.",
            "contact": contact,
        })
    return jobs


def _short_desc(text: str) -> str:
    if not text:
        return ""
    m = re.match(r'^(.{30,270}[.!?])\s', str(text))
    if m:
        return m.group(1)[:295]
    return str(text)[:295]


def _find_cover(id_code: str) -> str | None:
    for ext in ('.jpg', '.png', '.jpeg'):
        if (IMAGES_DST / (id_code + ext)).exists():
            return f"/static/uploads/{id_code}{ext}"
    return None


def _ensure_slug(title: str, used: set) -> str:
    base = slugify(title, lowercase=True) or "item"
    slug, i = base, 2
    while slug in used:
        slug = f"{base}-{i}"
        i += 1
    used.add(slug)
    return slug


def seed():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # ── Users ──────────────────────────────────────────────────────────
        admin = User(email="admin@investmap.ru", name="Администратор", role="admin")
        admin.set_password("admin123")
        mod = User(email="moderator@investmap.ru", name="Пётр Модератов", role="moderator")
        mod.set_password("moderator123")
        user1 = User(email="user@investmap.ru", name="Анна Иванова", role="user")
        user1.set_password("user1234")
        user2 = User(email="ivan@investmap.ru", name="Иван Петров", role="user")
        user2.set_password("user1234")
        investor = User(
            email="investor@investmap.ru", name="Сергей Инвестов", role="user",
            profile_type="investor", company_name="ООО «Дальневосточные инвестиции»",
            inn="2540123456", phone="+7 (423) 000-00-00",
            bio="Инвестиции в инфраструктурные и промышленные проекты Приморья.",
        )
        investor.set_password("invest1234")
        db.session.add_all([admin, mod, user1, user2, investor])
        db.session.flush()

        # ── Parse Excel ────────────────────────────────────────────────────
        wb = openpyxl.load_workbook(EXCEL_PATH)
        ws = wb["Проекты"]

        slugs: set = set()
        projects_buf: list = []   # (Project, id_code, jobs_text)
        initiatives: list = []

        for row in ws.iter_rows(values_only=True):
            item_id = str(row[1] or "").strip()
            if not item_id.startswith("#") or not row[2]:
                continue

            id_code = item_id.lstrip("#")          # e.g. "ВП1", "АИ5"
            district_letter = id_code[0]           # "В", "А", "У", "Н"
            item_kind = id_code[1]                 # "П" = project, "И" = initiative
            district = DISTRICT_MAP.get(district_letter, "Владивосток")

            title = str(row[2]).strip()
            description = str(row[3] or "").strip()
            cover = _find_cover(id_code)

            if item_kind == "П":
                # Projects: col6=status, col7=type, col8=address, col9=dates, col10=budget, col11=jobs
                status = STATUS_MAP.get(str(row[6] or "").strip(), "planned")
                proj_type = TYPE_MAP.get(str(row[7] or "").strip(), "infrastructure")
                lat, lng = _parse_coords(row[8])
                address = _parse_address(row[8])
                start_date, end_date = _parse_dates(row[9])
                budget = int(row[10]) if isinstance(row[10], (int, float)) else None
                responsible = str(row[4] or "").strip() or str(row[5] or "").strip()

                p = Project(
                    title=title,
                    slug=_ensure_slug(title, slugs),
                    short_description=_short_desc(description),
                    description=description,
                    type=proj_type, status=status, district=district,
                    lat=lat or 43.1, lng=lng or 131.88,
                    address=address,
                    start_date=start_date, end_date=end_date,
                    budget=budget, responsible=responsible,
                    cover=cover,
                )
                projects_buf.append((p, id_code, row[11]))

            elif item_kind == "И":
                # Initiatives: col6=status, col7=address, col8=dates, col9=goal_amount
                status_str = str(row[6] or "").strip()
                status = INITIATIVE_STATUS_MAP.get(status_str, "active")
                lat, lng = _parse_coords(row[7])
                _, end_date = _parse_dates(row[8])
                goal_amount = int(row[9]) if isinstance(row[9], (int, float)) else 0

                if status == "funded":
                    collected = goal_amount
                else:
                    pct = (abs(hash(title)) % 40 + 10) / 100
                    collected = int(goal_amount * pct)

                initiator = str(row[4] or "").strip()
                il = initiator.lower()
                if "физическое лицо" in il:
                    author_type = "citizen"
                elif any(w in il for w in ("нко", "фонд", "клуб")):
                    author_type = "ngo"
                else:
                    author_type = "municipality"

                ini = Initiative(
                    title=title,
                    slug=_ensure_slug(title, slugs),
                    short_description=_short_desc(description),
                    description=description,
                    author_type=author_type,
                    author_name=initiator,
                    district=district,
                    lat=lat or 43.1, lng=lng or 131.88,
                    goal_amount=goal_amount,
                    collected_amount=collected,
                    status=status,
                    cover=cover,
                    end_date=end_date or (date.today() + timedelta(days=120)),
                    views=abs(hash(title)) % 2000 + 50,
                )
                initiatives.append(ini)

        # ── Persist projects ───────────────────────────────────────────────
        for p, _, _ in projects_buf:
            db.session.add(p)
        db.session.flush()

        # ── Jobs ───────────────────────────────────────────────────────────
        for p, id_code, jobs_text in projects_buf:
            if p.status in ("planned", "in_progress"):
                for job_data in _parse_jobs(jobs_text, p.id):
                    db.session.add(Job(
                        project_id=p.id,
                        title=job_data["title"],
                        requirements=job_data["requirements"],
                        salary_min=job_data["salary_min"],
                        salary_max=job_data["salary_max"],
                        contact=job_data["contact"],
                    ))

        # ── Comments (chat) — 2 per project ───────────────────────────────
        for p, _, _ in projects_buf:
            chat = CHAT_TEMPLATES.get(p.type, _CHAT_DEFAULT)
            for body, is_mod in chat:
                author = mod if is_mod else user1
                db.session.add(Comment(
                    project_id=p.id,
                    user_id=author.id,
                    body=body,
                    is_moderator=is_mod,
                ))

        # ── Initiatives ────────────────────────────────────────────────────
        db.session.add_all(initiatives)
        db.session.flush()

        for ini in initiatives:
            for u in (user1, user2):
                if (u.id + ini.id) % 2 == 0:
                    db.session.add(InitiativeVote(user_id=u.id, initiative_id=ini.id))
            if ini.collected_amount > 0:
                db.session.add(Donation(
                    initiative_id=ini.id, user_id=user1.id,
                    amount=ini.collected_amount, anonymous=False,
                ))

        # ── Sample subscription + notification ────────────────────────────
        first_project = projects_buf[0][0]
        db.session.add(Subscription(user_id=user1.id, project_id=first_project.id))
        db.session.add(Notification(
            user_id=user1.id,
            title=f"Новости по проекту «{first_project.title}»",
            body="Обновлён статус реализации проекта.",
            link=f"/projects/{first_project.slug}",
        ))

        db.session.commit()

        n_proj = len(projects_buf)
        n_ini = len(initiatives)
        print(f"\n[OK] Загружено: {n_proj} проектов, {n_ini} инициатив.")
        print("  Логины:")
        print("    admin@investmap.ru      / admin123")
        print("    moderator@investmap.ru  / moderator123")
        print("    user@investmap.ru       / user1234")
        print("    investor@investmap.ru   / invest1234  (профиль инвестора)")


if __name__ == "__main__":
    seed()
