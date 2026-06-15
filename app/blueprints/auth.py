from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models import User


def _is_safe_url(target: str) -> bool:
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("cabinet.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Неверный email или пароль", "danger")
            return render_template("auth/login.html", email=email)
        login_user(user, remember=bool(request.form.get("remember")))
        flash(f"С возвращением, {user.name}!", "success")
        next_url = request.args.get("next")
        if not next_url or not _is_safe_url(next_url):
            next_url = url_for("cabinet.index")
        return redirect(next_url)
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("cabinet.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        if not (email and name and password):
            flash("Заполните все поля", "danger")
        elif password != password2:
            flash("Пароли не совпадают", "danger")
        elif len(password) < 6:
            flash("Пароль должен быть не короче 6 символов", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Пользователь с таким email уже зарегистрирован", "danger")
        else:
            user = User(email=email, name=name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Регистрация успешна!", "success")
            return redirect(url_for("cabinet.index"))
        return render_template("auth/register.html", email=email, name=name)
    return render_template("auth/register.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for("main.index"))
