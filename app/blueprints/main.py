from flask import Blueprint, render_template, current_app
from sqlalchemy import func
from ..models import Project, Initiative, Donation, InitiativeVote, User, Activity
from ..extensions import db

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    center = current_app.config["MAP_CENTER"]
    zoom = current_app.config["MAP_ZOOM"]
    project_count = Project.query.count()
    initiative_count = Initiative.query.count()
    total_raised = db.session.query(func.coalesce(func.sum(Donation.amount), 0)).scalar() or 0
    return render_template(
        "map.html",
        map_center=center,
        map_zoom=zoom,
        project_count=project_count,
        initiative_count=initiative_count,
        total_raised=total_raised,
    )


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/analytics")
def analytics():
    """Дашборд по всему порталу: проекты, инициативы, деньги."""
    # --- Totals ---
    totals = {
        "projects": Project.query.count(),
        "initiatives": Initiative.query.count(),
        "users": User.query.count(),
        "budget_sum": db.session.query(func.coalesce(func.sum(Project.budget), 0)).scalar() or 0,
        "raised_sum": db.session.query(func.coalesce(func.sum(Donation.amount), 0)).scalar() or 0,
        "votes_sum": db.session.query(func.count(InitiativeVote.id)).scalar() or 0,
    }

    # --- Проекты по типам ---
    by_type_rows = (
        db.session.query(Project.type, func.count(Project.id), func.coalesce(func.sum(Project.budget), 0))
        .group_by(Project.type).all()
    )
    type_labels_ru = {
        "infrastructure": "Инфраструктура", "ecology": "Экология", "business": "Бизнес",
        "social": "Социальный", "transport": "Транспорт", "education": "Образование", "culture": "Культура",
    }
    by_type = [
        {"label": type_labels_ru.get(t, t), "count": int(c), "budget": int(b)}
        for t, c, b in by_type_rows
    ]

    # --- Проекты по статусам ---
    by_status_rows = db.session.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
    status_labels_ru = {
        "planned": "Запланирован", "in_progress": "Реализуется",
        "completed": "Завершён", "paused": "Приостановлен",
    }
    by_status = [{"label": status_labels_ru.get(s, s), "count": int(c)} for s, c in by_status_rows]

    # --- Проекты по районам ---
    by_district_rows = (
        db.session.query(Project.district, func.count(Project.id), func.coalesce(func.sum(Project.budget), 0))
        .group_by(Project.district).order_by(func.count(Project.id).desc()).all()
    )
    by_district = [
        {"label": d, "count": int(c), "budget": int(b)}
        for d, c, b in by_district_rows
    ]

    # --- Инициативы: авторство ---
    author_rows = db.session.query(Initiative.author_type, func.count(Initiative.id)).group_by(Initiative.author_type).all()
    author_labels_ru = {"municipality": "Муниципалитет", "ngo": "НКО", "citizen": "Граждане"}
    by_author = [{"label": author_labels_ru.get(a, a), "count": int(c)} for a, c in author_rows]

    # --- Топ-районы по сборам инициатив ---
    district_collected_rows = (
        db.session.query(Initiative.district, func.coalesce(func.sum(Initiative.collected_amount), 0))
        .group_by(Initiative.district).order_by(func.sum(Initiative.collected_amount).desc()).limit(8).all()
    )
    district_collected = [{"label": d or "—", "amount": int(v)} for d, v in district_collected_rows]

    return render_template(
        "analytics.html",
        totals=totals,
        by_type=by_type,
        by_status=by_status,
        by_district=by_district,
        by_author=by_author,
        district_collected=district_collected,
    )
