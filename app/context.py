from flask import current_app
from flask_login import current_user
from .models import Notification, SupportTicket


def register_context(app):
    @app.context_processor
    def inject_globals():
        unread = 0
        open_tickets = 0
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
            if current_user.is_moderator:
                open_tickets = SupportTicket.query.filter_by(status="open").count()
        return {
            "DISTRICTS": current_app.config["DISTRICTS"],
            "PROJECT_TYPES": current_app.config["PROJECT_TYPES"],
            "PROJECT_STATUSES": current_app.config["PROJECT_STATUSES"],
            "unread_notifications": unread,
            "open_tickets_count": open_tickets,
        }

    @app.template_filter("money")
    def money(value):
        try:
            v = int(value or 0)
        except (TypeError, ValueError):
            return value
        return f"{v:,}".replace(",", " ") + " ₽"

    @app.template_filter("date_ru")
    def date_ru(value):
        if not value:
            return ""
        return value.strftime("%d.%m.%Y")
