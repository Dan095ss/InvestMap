from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from slugify import slugify
from ..extensions import db
from ..models import Initiative, InitiativeVote, Donation, log_activity, notify, User, Subscription

bp = Blueprint("initiatives", __name__)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    """Публичная подача инициативы гражданином. Создаётся со статусом 'moderation'."""
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        short = (request.form.get("short_description") or "").strip()
        description = (request.form.get("description") or "").strip()
        district = (request.form.get("district") or "").strip()
        try:
            lat = float(request.form.get("lat") or 0) or None
            lng = float(request.form.get("lng") or 0) or None
        except ValueError:
            lat, lng = None, None
        try:
            goal_amount = int(request.form.get("goal_amount") or 0)
        except ValueError:
            goal_amount = 0

        errors = []
        if len(title) < 5: errors.append("Название — минимум 5 символов")
        if len(short) < 10: errors.append("Краткое описание — минимум 10 символов")
        if len(description) < 30: errors.append("Подробное описание — минимум 30 символов")
        if not district: errors.append("Укажите район")
        if goal_amount < 1000: errors.append("Цель сбора — минимум 1 000 ₽")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("initiatives/new.html", form=request.form)

        # Уникальный slug
        base = slugify(title, lowercase=True) or "initiative"
        slug = base
        i = 2
        while Initiative.query.filter_by(slug=slug).first():
            slug = f"{base}-{i}"; i += 1

        initiative = Initiative(
            title=title, slug=slug,
            short_description=short, description=description,
            author_type="citizen", author_name=current_user.name,
            proposed_by_id=current_user.id,
            district=district, lat=lat, lng=lng,
            goal_amount=goal_amount, collected_amount=0,
            status="moderation",
            end_date=date.today() + timedelta(days=90),
        )
        db.session.add(initiative)
        log_activity(
            current_user, "proposal",
            f"Предложили инициативу «{title}» — отправлено на модерацию",
            url_for("initiatives.detail", slug=slug),
        )
        notify(
            current_user.id,
            "Инициатива отправлена на модерацию",
            f"Ваша инициатива «{title}» будет рассмотрена модератором.",
            url_for("initiatives.detail", slug=slug),
        )
        # Уведомим всех модераторов
        for m in User.query.filter(User.role.in_(["moderator", "admin"])).all():
            notify(m.id,
                   "Новая инициатива на модерации",
                   f"«{title}» от {current_user.name}",
                   url_for("initiatives.detail", slug=slug))
        db.session.commit()
        flash("Спасибо! Инициатива отправлена на модерацию.", "success")
        return redirect(url_for("initiatives.detail", slug=slug))

    return render_template("initiatives/new.html", form={})


@bp.route("/top")
def top():
    """Рейтинг инициатив: топ по голосам, по сборам, по свежести."""
    active_q = Initiative.query.filter(Initiative.status != "closed")

    # Топ по голосам
    top_votes = (
        active_q.outerjoin(InitiativeVote)
        .group_by(Initiative.id)
        .order_by(db.func.count(InitiativeVote.id).desc(), Initiative.created_at.desc())
        .limit(5)
        .all()
    )
    # Топ по собранной сумме
    top_collected = (
        Initiative.query.order_by(Initiative.collected_amount.desc()).limit(5).all()
    )
    # Топ по проценту исполнения
    all_with_goal = [i for i in Initiative.query.all() if i.goal_amount]
    top_progress = sorted(all_with_goal, key=lambda i: i.progress_pct, reverse=True)[:5]
    # Свежие
    top_new = Initiative.query.order_by(Initiative.created_at.desc()).limit(5).all()

    totals = {
        "count": Initiative.query.count(),
        "active": Initiative.query.filter_by(status="active").count(),
        "funded": Initiative.query.filter_by(status="funded").count(),
        "collected_sum": db.session.query(db.func.coalesce(db.func.sum(Initiative.collected_amount), 0)).scalar() or 0,
        "votes_sum": db.session.query(db.func.count(InitiativeVote.id)).scalar() or 0,
    }

    return render_template(
        "initiatives/top.html",
        top_votes=top_votes,
        top_collected=top_collected,
        top_progress=top_progress,
        top_new=top_new,
        totals=totals,
    )


@bp.route("/")
def list_initiatives():
    district = request.args.get("district")
    status = request.args.get("status")
    sort = request.args.get("sort", "new")  # new | popular | funded
    q = Initiative.query
    # Обычные пользователи не видят модерацию/отклонённые
    if not (current_user.is_authenticated and current_user.is_moderator):
        q = q.filter(Initiative.status.notin_(["moderation", "rejected"]))
    if district: q = q.filter_by(district=district)
    if status: q = q.filter_by(status=status)
    if sort == "popular":
        q = q.outerjoin(InitiativeVote).group_by(Initiative.id).order_by(db.func.count(InitiativeVote.id).desc())
    elif sort == "funded":
        q = q.order_by(Initiative.collected_amount.desc())
    elif sort == "views":
        q = q.order_by(Initiative.views.desc())
    else:
        q = q.order_by(Initiative.created_at.desc())
    initiatives = q.all()
    favorited_ids = set()
    if current_user.is_authenticated:
        favs = Subscription.query.filter(
            Subscription.user_id == current_user.id,
            Subscription.initiative_id.isnot(None),
        ).all()
        favorited_ids = {f.initiative_id for f in favs}
    return render_template(
        "initiatives/list.html",
        initiatives=initiatives,
        favorited_ids=favorited_ids,
        selected={"district": district, "status": status, "sort": sort},
    )


@bp.route("/<slug>")
def detail(slug):
    initiative = Initiative.query.filter_by(slug=slug).first_or_404()
    initiative.views = (initiative.views or 0) + 1
    db.session.commit()
    has_voted = False
    is_favorited = False
    if current_user.is_authenticated:
        has_voted = InitiativeVote.query.filter_by(
            user_id=current_user.id, initiative_id=initiative.id
        ).first() is not None
        is_favorited = Subscription.query.filter_by(
            user_id=current_user.id, initiative_id=initiative.id
        ).first() is not None
    return render_template(
        "initiatives/detail.html",
        initiative=initiative,
        has_voted=has_voted,
        is_favorited=is_favorited,
    )


@bp.route("/<slug>/favorite", methods=["POST"])
@login_required
def favorite(slug):
    initiative = Initiative.query.filter_by(slug=slug).first_or_404()
    existing = Subscription.query.filter_by(
        user_id=current_user.id, initiative_id=initiative.id
    ).first()
    if existing:
        db.session.delete(existing)
        flash("Инициатива удалена из избранного", "info")
        action = "Убрали из избранного"
    else:
        sub = Subscription(user_id=current_user.id, initiative_id=initiative.id)
        db.session.add(sub)
        flash("Инициатива добавлена в избранное", "success")
        action = "Добавили в избранное"
        notify(
            current_user.id,
            f"Инициатива в избранном: «{initiative.title}»",
            "Вы будете получать уведомления о ходе реализации и сборе средств.",
            url_for("initiatives.detail", slug=slug),
        )
    log_activity(
        current_user, "favorite",
        f"{action}: «{initiative.title}»",
        url_for("initiatives.detail", slug=slug),
    )
    db.session.commit()
    next_url = request.form.get("next") or url_for("initiatives.detail", slug=slug)
    return redirect(next_url)


@bp.route("/<slug>/vote", methods=["POST"])
@login_required
def vote(slug):
    initiative = Initiative.query.filter_by(slug=slug).first_or_404()
    existing = InitiativeVote.query.filter_by(
        user_id=current_user.id, initiative_id=initiative.id
    ).first()
    if existing:
        db.session.delete(existing)
        flash("Голос отозван", "info")
        action = "Отозвали голос"
    else:
        try:
            db.session.add(InitiativeVote(user_id=current_user.id, initiative_id=initiative.id))
            db.session.flush()
            flash("Ваш голос учтён", "success")
            action = "Проголосовали"
        except IntegrityError:
            db.session.rollback()
            flash("Голос уже был учтён", "info")
            return redirect(url_for("initiatives.detail", slug=slug))
    log_activity(
        current_user, "vote",
        f"{action} за «{initiative.title}»",
        url_for("initiatives.detail", slug=slug),
    )
    db.session.commit()
    return redirect(url_for("initiatives.detail", slug=slug))


@bp.route("/<slug>/donate", methods=["POST"])
@login_required
def donate(slug):
    initiative = Initiative.query.filter_by(slug=slug).first_or_404()
    try:
        amount = int(request.form.get("amount", "0"))
    except ValueError:
        amount = 0
    if amount < 100:
        flash("Минимальная сумма взноса — 100 ₽", "danger")
        return redirect(url_for("initiatives.detail", slug=slug) + "#donate")
    anonymous = bool(request.form.get("anonymous"))
    donation = Donation(
        initiative_id=initiative.id,
        user_id=current_user.id,
        amount=amount,
        anonymous=anonymous,
    )
    initiative.collected_amount = (initiative.collected_amount or 0) + amount
    if initiative.goal_amount and initiative.collected_amount >= initiative.goal_amount:
        initiative.status = "funded"
    db.session.add(donation)
    log_activity(
        current_user, "donation",
        f"Взнос {amount} ₽ в инициативу «{initiative.title}»",
        url_for("initiatives.detail", slug=slug),
    )
    notify(
        current_user.id,
        "Спасибо за поддержку!",
        f"Ваш взнос {amount} ₽ зачислен в инициативу «{initiative.title}».",
        url_for("initiatives.detail", slug=slug),
    )
    db.session.commit()
    flash(f"Спасибо! Ваш взнос {amount} ₽ принят (демо, без реальной оплаты).", "success")
    return redirect(url_for("initiatives.detail", slug=slug) + "#donate")
