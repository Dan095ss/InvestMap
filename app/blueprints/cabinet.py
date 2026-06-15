from datetime import datetime
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import (
    Subscription, Notification, Activity, SupportTicket, Donation,
    InitiativeVote, Initiative, Project, InvestorInterest, log_activity,
)

bp = Blueprint("cabinet", __name__)


def _is_safe_url(target: str) -> bool:
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


def _get_achievements(user):
    votes = InitiativeVote.query.filter_by(user_id=user.id).count()
    donations = Donation.query.filter_by(user_id=user.id).count()
    donation_sum = (
        db.session.query(db.func.coalesce(db.func.sum(Donation.amount), 0))
        .filter(Donation.user_id == user.id).scalar() or 0
    )
    subs = Subscription.query.filter_by(user_id=user.id).count()
    proposals = Initiative.query.filter_by(proposed_by_id=user.id).count()
    favorites = Subscription.query.filter(
        Subscription.user_id == user.id,
        Subscription.initiative_id.isnot(None)
    ).count()

    earned = []
    if votes >= 1:
        earned.append({"icon": "⭐", "title": "Первый голос", "desc": "Проголосовали за инициативу"})
    if votes >= 5:
        earned.append({"icon": "🗳️", "title": "Активный гражданин", "desc": f"{votes} голосов отдано"})
    if votes >= 10:
        earned.append({"icon": "🏅", "title": "Народный эксперт", "desc": "10+ голосов"})
    if donations >= 1:
        earned.append({"icon": "💚", "title": "Первый взнос", "desc": "Поддержали инициативу рублём"})
    if donations >= 3:
        earned.append({"icon": "🤝", "title": "Спонсор", "desc": f"{donations} взноса сделано"})
    if donation_sum >= 5000:
        earned.append({"icon": "💎", "title": "Меценат", "desc": f"Вложено {donation_sum:,.0f} ₽".replace(",", " ")})
    if proposals >= 1:
        earned.append({"icon": "🚀", "title": "Инициатор", "desc": "Предложили инициативу жителей"})
    if subs >= 1:
        earned.append({"icon": "🔔", "title": "Подписчик", "desc": "Следите за проектами района"})
    if favorites >= 3:
        earned.append({"icon": "📌", "title": "Куратор", "desc": "3+ инициативы в избранном"})
    if not earned:
        earned.append({"icon": "🌱", "title": "Новичок", "desc": "Начните участвовать — голосуйте, вносите средства"})
    return earned


@bp.route("/")
@login_required
def index():
    sub_count = Subscription.query.filter_by(user_id=current_user.id).count()
    activity_count = Activity.query.filter_by(user_id=current_user.id).count()
    donation_sum = (
        db.session.query(db.func.coalesce(db.func.sum(Donation.amount), 0))
        .filter(Donation.user_id == current_user.id).scalar()
    )
    votes = InitiativeVote.query.filter_by(user_id=current_user.id).count()
    recent = (
        Activity.query.filter_by(user_id=current_user.id)
        .order_by(Activity.created_at.desc()).limit(8).all()
    )
    achievements = _get_achievements(current_user)
    return render_template(
        "cabinet/index.html",
        sub_count=sub_count,
        activity_count=activity_count,
        donation_sum=donation_sum or 0,
        votes=votes,
        recent=recent,
        achievements=achievements,
    )


@bp.route("/subscriptions", methods=["GET", "POST"])
@login_required
def subscriptions():
    if request.method == "POST":
        district = request.form.get("district")
        if district:
            exists = Subscription.query.filter_by(
                user_id=current_user.id, district=district
            ).first()
            if exists:
                flash("Вы уже подписаны на этот район", "info")
            else:
                db.session.add(Subscription(user_id=current_user.id, district=district))
                log_activity(current_user, "subscription", f"Подписка на район «{district}»")
                db.session.commit()
                flash(f"Вы подписались на район «{district}»", "success")
        return redirect(url_for("cabinet.subscriptions"))

    subs = Subscription.query.filter_by(user_id=current_user.id).order_by(
        Subscription.created_at.desc()
    ).all()
    return render_template("cabinet/subscriptions.html", subs=subs)


@bp.route("/subscriptions/<int:sub_id>/remove", methods=["POST"])
@login_required
def remove_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.user_id != current_user.id:
        flash("Нет прав", "danger")
        return redirect(url_for("cabinet.subscriptions"))
    db.session.delete(sub)
    db.session.commit()
    flash("Подписка удалена", "info")
    return redirect(url_for("cabinet.subscriptions"))


@bp.route("/notifications")
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).all()
    # отметим как прочитанные при посещении (с небольшой задержкой — после рендера тоже можно, но проще так)
    # Сохраним состояние, оставим маркер «unread» для UI — отметим только при клике
    return render_template("cabinet/notifications.html", items=items)


@bp.route("/notifications/read/<int:note_id>", methods=["POST"])
@login_required
def read_notification(note_id):
    n = Notification.query.get_or_404(note_id)
    if n.user_id != current_user.id:
        return redirect(url_for("cabinet.notifications"))
    n.is_read = True
    db.session.commit()
    link = n.link
    if not link or not _is_safe_url(link):
        link = url_for("cabinet.notifications")
    return redirect(link)


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
    flash("Все уведомления отмечены как прочитанные", "success")
    return redirect(url_for("cabinet.notifications"))


@bp.route("/activity")
@login_required
def activity():
    items = Activity.query.filter_by(user_id=current_user.id).order_by(
        Activity.created_at.desc()
    ).all()
    return render_template("cabinet/activity.html", items=items)


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = (request.form.get("name") or current_user.name).strip()
        current_user.profile_type = request.form.get("profile_type") or "physical"
        current_user.phone = (request.form.get("phone") or "").strip() or None
        current_user.bio = (request.form.get("bio") or "").strip() or None
        current_user.email_notifications = bool(request.form.get("email_notifications"))
        if current_user.profile_type == "investor":
            current_user.company_name = (request.form.get("company_name") or "").strip() or None
            current_user.inn = (request.form.get("inn") or "").strip() or None
        else:
            current_user.company_name = None
            current_user.inn = None
        db.session.commit()
        flash("Профиль обновлён", "success")
        return redirect(url_for("cabinet.profile"))
    return render_template("cabinet/profile.html")


@bp.route("/interests")
@login_required
def interests():
    """Мои заявки инвестиционного интереса."""
    items = (
        InvestorInterest.query.filter_by(user_id=current_user.id)
        .order_by(InvestorInterest.created_at.desc()).all()
    )
    return render_template("cabinet/interests.html", items=items)


@bp.route("/support", methods=["GET", "POST"])
@login_required
def support():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        if not (subject and body):
            flash("Заполните тему и сообщение", "danger")
        else:
            ticket = SupportTicket(user_id=current_user.id, subject=subject, body=body)
            db.session.add(ticket)
            log_activity(current_user, "support", f"Обращение в ТП: {subject}")
            db.session.commit()
            flash("Запрос отправлен в службу поддержки", "success")
        return redirect(url_for("cabinet.support"))

    tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(
        SupportTicket.created_at.desc()
    ).all()
    return render_template("cabinet/support.html", tickets=tickets)
