import os
from flask import Flask, redirect, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, JWTManager
from dotenv import load_dotenv

from app.config import config_map
from app.extensions import db, bcrypt, jwt, migrate, mail, csrf


def create_app(config_name=None):
    load_dotenv()

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)

    # API blueprints are JSON-only and authenticate via JWT cookie + CSRF
    # double-submit header, not the WTForms session CSRF token, so they're
    # exempted from Flask-WTF's CSRFProtect (which targets form posts).
    _register_blueprints(app, csrf)

    @app.route("/")
    def root():
        return redirect("/login")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden."}), 403

    @app.context_processor
    def inject_role_labels():
        from app.models.user import ROLE_LABELS
        return {"ROLE_LABELS": ROLE_LABELS}

    return app


def _register_blueprints(app, csrf):
    from app.auth.routes import bp as auth_bp
    from app.curriculum.routes import bp as curriculum_bp
    from app.dashboards.lecturer import bp as lecturer_bp
    from app.dashboards.hod import bp as hod_bp
    from app.dashboards.dean import bp as dean_bp
    from app.dashboards.qa import bp as qa_bp
    from app.dashboards.admin import bp as admin_bp
    from app.dashboards.notifications import bp as notifications_bp
    from app.reports.routes import bp as reports_bp
    from app.views import bp as views_bp

    for bp in (auth_bp, curriculum_bp, admin_bp, notifications_bp, reports_bp):
        csrf.exempt(bp)

    app.register_blueprint(auth_bp)
    app.register_blueprint(curriculum_bp)
    app.register_blueprint(lecturer_bp)
    app.register_blueprint(hod_bp)
    app.register_blueprint(dean_bp)
    app.register_blueprint(qa_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(views_bp)
