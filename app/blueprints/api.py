from flask import Blueprint, jsonify, request, url_for
from ..models import Project, Initiative

bp = Blueprint("api", __name__)


@bp.route("/projects")
def projects():
    q = Project.query
    type_ = request.args.getlist("type")
    status = request.args.getlist("status")
    district = request.args.getlist("district")
    search = request.args.get("q", "").strip()

    if type_:
        q = q.filter(Project.type.in_(type_))
    if status:
        q = q.filter(Project.status.in_(status))
    if district:
        q = q.filter(Project.district.in_(district))
    if search:
        pattern = f"%{search}%"
        q = q.filter((Project.title.ilike(pattern)) | (Project.description.ilike(pattern)))

    items = []
    for p in q.all():
        items.append({
            "id": p.id,
            "title": p.title,
            "short": p.short_description,
            "type": p.type,
            "status": p.status,
            "district": p.district,
            "lat": p.lat,
            "lng": p.lng,
            "url": url_for("projects.detail", slug=p.slug),
            "budget": p.budget,
        })
    return jsonify({"count": len(items), "items": items})


@bp.route("/initiatives")
def initiatives():
    # На карте не показываем модерируемые/отклонённые
    q = Initiative.query.filter(Initiative.status.notin_(["moderation", "rejected"]))
    items = []
    for i in q.all():
        if i.lat is None or i.lng is None:
            continue
        items.append({
            "id": i.id,
            "title": i.title,
            "short": i.short_description,
            "lat": i.lat,
            "lng": i.lng,
            "progress": i.progress_pct,
            "collected": i.collected_amount,
            "goal": i.goal_amount,
            "url": url_for("initiatives.detail", slug=i.slug),
        })
    return jsonify({"count": len(items), "items": items})
