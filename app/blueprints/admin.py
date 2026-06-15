"""Простая самописная админ-панель.

- Доступ: admin ко всему, moderator — только модерация инициатив + заявки интереса.
- CRUD: Projects, Initiatives, Users (только admin).
"""
from datetime import date, datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from slugify import slugify
from ..extensions import db
from ..models import (
    Project, Initiative, User, InvestorInterest, TimelineEvent, Job,
    ProjectMedia, Comment, Donation, InitiativeVote, SupportTicket, notify, log_activity,
)

bp = Blueprint("admin", __name__)


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


def moderator_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_moderator:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


# ---------- Dashboard ----------
@bp.route("/")
@moderator_required
def index():
    counts = {
        "projects": Project.query.count(),
        "initiatives": Initiative.query.count(),
        "users": User.query.count(),
        "moderation": Initiative.query.filter_by(status="moderation").count(),
        "interests_new": InvestorInterest.query.filter_by(status="new").count(),
    }
    pending_initiatives = (
        Initiative.query.filter_by(status="moderation")
        .order_by(Initiative.created_at.desc()).limit(10).all()
    )
    recent_interests = (
        InvestorInterest.query.order_by(InvestorInterest.created_at.desc()).limit(10).all()
    )
    return render_template("admin/index.html",
                           counts=counts,
                           pending_initiatives=pending_initiatives,
                           recent_interests=recent_interests)


# ---------- Projects CRUD ----------
@bp.route("/projects")
@admin_required
def projects_list():
    q = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("admin/projects_list.html", projects=q)


@bp.route("/projects/new", methods=["GET", "POST"])
@bp.route("/projects/<int:pid>/edit", methods=["GET", "POST"])
@admin_required
def project_form(pid=None):
    project = Project.query.get_or_404(pid) if pid else None
    if request.method == "POST":
        data = request.form
        if not project:
            project = Project(
                title=data["title"],
                slug="",  # set below
                short_description=data["short_description"],
                description=data["description"],
                type=data["type"], status=data["status"], district=data["district"],
                lat=float(data["lat"]), lng=float(data["lng"]),
            )
            db.session.add(project)
        else:
            project.title = data["title"]
            project.short_description = data["short_description"]
            project.description = data["description"]
            project.type = data["type"]
            project.status = data["status"]
            project.district = data["district"]
            project.lat = float(data["lat"])
            project.lng = float(data["lng"])

        # Optional fields
        project.goal = data.get("goal") or None
        project.address = data.get("address") or None
        project.responsible = data.get("responsible") or None
        project.budget = int(data["budget"]) if data.get("budget") else None
        project.start_date = datetime.strptime(data["start_date"], "%Y-%m-%d").date() if data.get("start_date") else None
        project.end_date = datetime.strptime(data["end_date"], "%Y-%m-%d").date() if data.get("end_date") else None

        # Slug
        if not project.slug:
            base = slugify(project.title, lowercase=True) or "project"
            slug = base; i = 2
            while Project.query.filter_by(slug=slug).filter(Project.id != (project.id or -1)).first():
                slug = f"{base}-{i}"; i += 1
            project.slug = slug

        db.session.commit()
        flash("Проект сохранён", "success")
        return redirect(url_for("admin.projects_list"))
    return render_template("admin/project_form.html", project=project)


@bp.route("/projects/<int:pid>/delete", methods=["POST"])
@admin_required
def project_delete(pid):
    p = Project.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash(f"Проект «{p.title}» удалён", "info")
    return redirect(url_for("admin.projects_list"))


# ---------- Initiatives CRUD + Moderation ----------
@bp.route("/initiatives")
@moderator_required
def initiatives_list():
    q = Initiative.query.order_by(Initiative.created_at.desc()).all()
    return render_template("admin/initiatives_list.html", initiatives=q)


@bp.route("/initiatives/new", methods=["GET", "POST"])
@bp.route("/initiatives/<int:iid>/edit", methods=["GET", "POST"])
@admin_required
def initiative_form(iid=None):
    initiative = Initiative.query.get_or_404(iid) if iid else None
    if request.method == "POST":
        data = request.form
        if not initiative:
            initiative = Initiative(
                title=data["title"], slug="",
                short_description=data["short_description"],
                description=data["description"],
                author_type=data.get("author_type", "municipality"),
                author_name=data.get("author_name"),
                district=data.get("district"),
                goal_amount=int(data.get("goal_amount") or 0),
                status=data.get("status", "active"),
            )
            db.session.add(initiative)
        else:
            initiative.title = data["title"]
            initiative.short_description = data["short_description"]
            initiative.description = data["description"]
            initiative.author_type = data.get("author_type") or "municipality"
            initiative.author_name = data.get("author_name")
            initiative.district = data.get("district")
            initiative.goal_amount = int(data.get("goal_amount") or 0)
            initiative.status = data.get("status") or "active"
        initiative.lat = float(data["lat"]) if data.get("lat") else None
        initiative.lng = float(data["lng"]) if data.get("lng") else None
        initiative.collected_amount = int(data.get("collected_amount") or 0)

        if not initiative.slug:
            base = slugify(initiative.title, lowercase=True) or "initiative"
            slug = base; i = 2
            while Initiative.query.filter_by(slug=slug).filter(Initiative.id != (initiative.id or -1)).first():
                slug = f"{base}-{i}"; i += 1
            initiative.slug = slug
        db.session.commit()
        flash("Инициатива сохранена", "success")
        return redirect(url_for("admin.initiatives_list"))
    return render_template("admin/initiative_form.html", initiative=initiative)


@bp.route("/initiatives/<int:iid>/approve", methods=["POST"])
@moderator_required
def initiative_approve(iid):
    i = Initiative.query.get_or_404(iid)
    i.status = "active"
    if i.proposed_by_id:
        notify(i.proposed_by_id, "Ваша инициатива одобрена!",
               f"«{i.title}» опубликована и начала сбор поддержки.",
               url_for("initiatives.detail", slug=i.slug))
    db.session.commit()
    flash(f"Инициатива «{i.title}» одобрена", "success")
    return redirect(url_for("admin.initiatives_list"))


@bp.route("/initiatives/<int:iid>/reject", methods=["POST"])
@moderator_required
def initiative_reject(iid):
    i = Initiative.query.get_or_404(iid)
    reason = (request.form.get("reason") or "").strip()
    i.status = "rejected"
    if i.proposed_by_id:
        notify(i.proposed_by_id, "Инициатива отклонена",
               f"«{i.title}»: {reason or 'не прошла модерацию'}.",
               url_for("initiatives.detail", slug=i.slug))
    db.session.commit()
    flash(f"Инициатива «{i.title}» отклонена", "info")
    return redirect(url_for("admin.initiatives_list"))


@bp.route("/initiatives/<int:iid>/delete", methods=["POST"])
@admin_required
def initiative_delete(iid):
    i = Initiative.query.get_or_404(iid)
    db.session.delete(i); db.session.commit()
    flash(f"Инициатива «{i.title}» удалена", "info")
    return redirect(url_for("admin.initiatives_list"))


# ---------- Users CRUD ----------
@bp.route("/users")
@admin_required
def users_list():
    q = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users_list.html", users=q)


@bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(uid):
    u = User.query.get_or_404(uid)
    if request.method == "POST":
        u.name = request.form.get("name") or u.name
        u.role = request.form.get("role") or "user"
        u.profile_type = request.form.get("profile_type") or "physical"
        u.company_name = request.form.get("company_name") or None
        u.inn = request.form.get("inn") or None
        db.session.commit()
        flash(f"Пользователь {u.email} обновлён", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", user=u)


@bp.route("/users/<int:uid>/delete", methods=["POST"])
@admin_required
def user_delete(uid):
    u = User.query.get_or_404(uid)
    if u.id == current_user.id:
        flash("Нельзя удалить самого себя", "danger")
        return redirect(url_for("admin.users_list"))
    db.session.delete(u); db.session.commit()
    flash(f"Пользователь {u.email} удалён", "info")
    return redirect(url_for("admin.users_list"))


# ---------- Investor Interests ----------
@bp.route("/interests")
@moderator_required
def interests_list():
    q = InvestorInterest.query.order_by(InvestorInterest.created_at.desc()).all()
    return render_template("admin/interests_list.html", interests=q)


@bp.route("/interests/<int:iid>/status", methods=["POST"])
@moderator_required
def interest_set_status(iid):
    it = InvestorInterest.query.get_or_404(iid)
    new_status = request.form.get("status")
    if new_status in ("new", "reviewed", "accepted", "declined"):
        it.status = new_status
        notify(it.user_id,
               "Обновление по вашей заявке",
               f"Заявка к «{it.project.title}»: статус «{new_status}».",
               url_for("cabinet.interests"))
        db.session.commit()
        flash("Статус обновлён", "success")
    return redirect(url_for("admin.interests_list"))


# ---------- Support Tickets ----------
@bp.route("/tickets")
@moderator_required
def tickets_list():
    status_filter = request.args.get("status", "")
    q = SupportTicket.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    tickets = q.order_by(SupportTicket.created_at.desc()).all()
    counts = {
        "open": SupportTicket.query.filter_by(status="open").count(),
        "answered": SupportTicket.query.filter_by(status="answered").count(),
        "closed": SupportTicket.query.filter_by(status="closed").count(),
    }
    return render_template("admin/tickets_list.html",
                           tickets=tickets, counts=counts, status_filter=status_filter)


@bp.route("/tickets/<int:tid>/reply", methods=["POST"])
@moderator_required
def ticket_reply(tid):
    ticket = SupportTicket.query.get_or_404(tid)
    reply = (request.form.get("reply") or "").strip()
    if not reply:
        flash("Текст ответа не может быть пустым", "danger")
        return redirect(url_for("admin.tickets_list"))
    ticket.reply = reply
    ticket.status = "answered"
    ticket.answered_at = datetime.utcnow()
    db.session.commit()
    notify(ticket.user_id,
           f"Ответ на ваш запрос: {ticket.subject}",
           reply[:200],
           url_for("cabinet.support"))
    flash(f"Ответ отправлен пользователю {ticket.user.name}", "success")
    return redirect(url_for("admin.tickets_list"))


@bp.route("/tickets/<int:tid>/close", methods=["POST"])
@moderator_required
def ticket_close(tid):
    ticket = SupportTicket.query.get_or_404(tid)
    ticket.status = "closed"
    db.session.commit()
    flash("Тикет закрыт", "info")
    return redirect(url_for("admin.tickets_list"))


# ---------- Comments Moderation ----------
@bp.route("/comments")
@moderator_required
def comments_list():
    project_filter = request.args.get("project_id", type=int)
    q = Comment.query.order_by(Comment.created_at.desc())
    if project_filter:
        q = q.filter_by(project_id=project_filter)
    comments = q.limit(100).all()
    projects = Project.query.order_by(Project.title).all()
    return render_template("admin/comments_list.html",
                           comments=comments, projects=projects,
                           project_filter=project_filter)


@bp.route("/comments/<int:cid>/delete", methods=["POST"])
@moderator_required
def comment_delete(cid):
    c = Comment.query.get_or_404(cid)
    project_id = c.project_id
    db.session.delete(c)
    db.session.commit()
    flash("Комментарий удалён", "info")
    back = request.form.get("back") or url_for("admin.comments_list")
    return redirect(back)
