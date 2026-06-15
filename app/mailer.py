"""Простая отправка email без внешних зависимостей.

Если MAIL_ENABLED = False (dev по умолчанию) — письма попадают в лог Flask.
Если MAIL_ENABLED = True — реально шлёт через SMTP (нужны MAIL_* переменные окружения).
"""
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from email.header import Header
from flask import current_app, url_for


def _build_message(subject, body, to_email, from_addr, from_name):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(from_name, "utf-8")), from_addr))
    msg["To"] = to_email
    return msg


def send_email(to_email, subject, body):
    """Послать одно письмо. Ничего не бросает — только логирует."""
    cfg = current_app.config
    enabled = cfg.get("MAIL_ENABLED", False)
    from_addr = cfg.get("MAIL_FROM", "no-reply@investmap.ru")
    from_name = cfg.get("MAIL_FROM_NAME", "InvestMap")

    if not to_email:
        return False

    if not enabled:
        # Dev-режим: просто логируем
        current_app.logger.info(
            "[MAIL:dev] to=%s subject=%s\n%s", to_email, subject, body
        )
        return True

    try:
        msg = _build_message(subject, body, to_email, from_addr, from_name)
        server = cfg.get("MAIL_SERVER")
        port = cfg.get("MAIL_PORT", 587)
        use_tls = cfg.get("MAIL_USE_TLS", True)
        with smtplib.SMTP(server, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            username = cfg.get("MAIL_USERNAME")
            password = cfg.get("MAIL_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(from_addr, [to_email], msg.as_string())
        current_app.logger.info("[MAIL:sent] to=%s subject=%s", to_email, subject)
        return True
    except Exception as exc:
        current_app.logger.warning("[MAIL:failed] to=%s err=%s", to_email, exc)
        return False


def notify_by_email(user, title, body=None, link=None):
    """Высокоуровневая обёртка: шлёт если у пользователя включены email-уведомления."""
    if not user or not user.email:
        return False
    if not getattr(user, "email_notifications", True):
        return False
    full_body = (body or "") + "\n\n"
    if link:
        try:
            full_body += url_for("main.index", _external=True).rstrip("/") + link + "\n"
        except Exception:
            full_body += link + "\n"
    full_body += "\n— InvestMap, портал инвестиционных проектов Приморского края"
    return send_email(user.email, title, full_body)
