import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from ..extensions import db
from ..models import Project, Comment, ProjectMedia, log_activity, notify, Subscription, InvestorInterest, User

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_DOC_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"}

bp = Blueprint("projects", __name__)


@bp.route("/")
def list_projects():
    q = Project.query
    type_ = request.args.get("type")
    status = request.args.get("status")
    district = request.args.get("district")
    search = request.args.get("q", "").strip()

    if type_: q = q.filter_by(type=type_)
    if status: q = q.filter_by(status=status)
    if district: q = q.filter_by(district=district)
    if search:
        pattern = f"%{search}%"
        q = q.filter((Project.title.ilike(pattern)) | (Project.description.ilike(pattern)))

    projects = q.order_by(Project.created_at.desc()).all()
    return render_template(
        "projects/list.html",
        projects=projects,
        selected={"type": type_, "status": status, "district": district, "q": search},
    )


@bp.route("/<slug>")
def detail(slug):
    project = Project.query.filter_by(slug=slug).first_or_404()
    is_subscribed = False
    if current_user.is_authenticated:
        is_subscribed = Subscription.query.filter_by(
            user_id=current_user.id, project_id=project.id
        ).first() is not None
    return render_template("projects/detail.html", project=project, is_subscribed=is_subscribed)


@bp.route("/<slug>/comment", methods=["POST"])
@login_required
def post_comment(slug):
    project = Project.query.filter_by(slug=slug).first_or_404()
    body = request.form.get("body", "").strip()
    if not body:
        flash("Введите текст комментария", "danger")
        return redirect(url_for("projects.detail", slug=slug) + "#comments")
    comment = Comment(
        project_id=project.id,
        user_id=current_user.id,
        body=body,
        is_moderator=current_user.is_moderator,
    )
    db.session.add(comment)
    log_activity(
        current_user, "comment",
        f"Комментарий к проекту «{project.title}»",
        url_for("projects.detail", slug=slug),
    )
    # notify subscribers
    subs = Subscription.query.filter_by(project_id=project.id).all()
    for s in subs:
        if s.user_id != current_user.id:
            notify(
                s.user_id,
                f"Новый комментарий: {project.title}",
                body[:140],
                url_for("projects.detail", slug=slug) + "#comments",
            )
    db.session.commit()
    flash("Комментарий добавлен", "success")
    return redirect(url_for("projects.detail", slug=slug) + "#comments")


@bp.route("/<slug>/interest", methods=["POST"])
@login_required
def submit_interest(slug):
    """Инвестор отправляет заявку интереса к проекту."""
    project = Project.query.filter_by(slug=slug).first_or_404()
    if not current_user.is_investor:
        flash("Заявки интереса могут подавать только инвесторы. Заполните профиль инвестора.", "danger")
        return redirect(url_for("cabinet.profile"))

    try:
        amount = int(request.form.get("amount") or 0)
    except ValueError:
        amount = 0
    message = (request.form.get("message") or "").strip()
    contact = (request.form.get("contact") or "").strip() or None

    if len(message) < 20:
        flash("Сообщение должно быть минимум 20 символов", "danger")
        return redirect(url_for("projects.detail", slug=slug) + "#interest")

    interest = InvestorInterest(
        user_id=current_user.id, project_id=project.id,
        amount=amount if amount > 0 else None,
        message=message, contact=contact, status="new",
    )
    db.session.add(interest)
    log_activity(
        current_user, "interest",
        f"Заявка интереса: «{project.title}»",
        url_for("projects.detail", slug=slug),
    )
    notify(
        current_user.id,
        "Заявка интереса отправлена",
        f"Команда проекта «{project.title}» свяжется с вами.",
        url_for("cabinet.interests"),
    )
    # уведомим модераторов
    for m in User.query.filter(User.role.in_(["moderator", "admin"])).all():
        notify(m.id,
               "Новая заявка инвестора",
               f"{current_user.company_name or current_user.name} — «{project.title}»",
               url_for("projects.detail", slug=slug))
    db.session.commit()
    flash("Заявка отправлена. Команда проекта свяжется с вами.", "success")
    return redirect(url_for("projects.detail", slug=slug) + "#interest")


@bp.route("/<slug>/media", methods=["POST"])
@login_required
def upload_media(slug):
    """Загрузка фото/документа. Только для модераторов/админов."""
    if not current_user.is_moderator:
        abort(403)
    project = Project.query.filter_by(slug=slug).first_or_404()
    f = request.files.get("file")
    caption = (request.form.get("caption") or "").strip() or None
    if not f or not f.filename:
        flash("Выберите файл для загрузки", "danger")
        return redirect(url_for("projects.detail", slug=slug))

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_IMAGE_EXT and ext not in ALLOWED_DOC_EXT:
        flash(f"Недопустимый формат: .{ext}", "danger")
        return redirect(url_for("projects.detail", slug=slug))

    kind = "photo" if ext in ALLOWED_IMAGE_EXT else "document"
    safe_name = secure_filename(f.filename) or f"file.{ext}"
    unique = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, unique)
    f.save(save_path)
    url = url_for("static", filename=f"uploads/{unique}")

    media = ProjectMedia(project_id=project.id, kind=kind, url=url, caption=caption)
    db.session.add(media)
    log_activity(current_user, "media", f"Загрузили {kind} к «{project.title}»",
                 url_for("projects.detail", slug=slug))
    db.session.commit()
    flash("Файл загружен", "success")
    return redirect(url_for("projects.detail", slug=slug))


@bp.route("/<slug>/media/<int:media_id>/delete", methods=["POST"])
@login_required
def delete_media(slug, media_id):
    if not current_user.is_moderator:
        abort(403)
    m = ProjectMedia.query.get_or_404(media_id)
    if m.project.slug != slug:
        abort(404)
    # Удалим файл с диска (best-effort)
    if m.url.startswith("/static/uploads/"):
        path = os.path.join(current_app.root_path, m.url.lstrip("/").replace("/", os.sep))
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    db.session.delete(m)
    db.session.commit()
    flash("Файл удалён", "info")
    return redirect(url_for("projects.detail", slug=slug))


@bp.route("/<slug>/subscribe", methods=["POST"])
@login_required
def subscribe(slug):
    project = Project.query.filter_by(slug=slug).first_or_404()
    existing = Subscription.query.filter_by(
        user_id=current_user.id, project_id=project.id
    ).first()
    if existing:
        db.session.delete(existing)
        flash("Подписка отменена", "info")
        action = "Отписались от проекта"
    else:
        sub = Subscription(user_id=current_user.id, project_id=project.id)
        db.session.add(sub)
        flash("Вы подписались на проект", "success")
        action = "Подписались на проект"
    log_activity(
        current_user, "subscription",
        f"{action} «{project.title}»",
        url_for("projects.detail", slug=slug),
    )
    db.session.commit()
    return redirect(url_for("projects.detail", slug=slug))
