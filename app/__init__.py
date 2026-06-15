import os
from flask import Flask
from config import Config
from .extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is not configured. "
            "Set the SECRET_KEY environment variable. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    from .blueprints.main import bp as main_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.projects import bp as projects_bp
    from .blueprints.initiatives import bp as initiatives_bp
    from .blueprints.cabinet import bp as cabinet_bp
    from .blueprints.api import bp as api_bp
    from .blueprints.admin import bp as admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(initiatives_bp, url_prefix="/initiatives")
    app.register_blueprint(cabinet_bp, url_prefix="/cabinet")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from .context import register_context
    register_context(app)

    with app.app_context():
        db.create_all()

    return app
