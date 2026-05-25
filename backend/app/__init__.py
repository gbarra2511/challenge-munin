"""App factory do Mini-WFM.

`create_app()` monta a aplicação Flask: injeta config, liga a sessão de DB
ao ciclo de request, registra error handlers JSON, CORS e os blueprints.
Testes podem injetar `settings` e um `session_factory` ligado a uma
transação que sofre rollback.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, jsonify, request

from app.api.errors import register_error_handlers
from app.infra.config import Settings, get_settings
from app.infra.db import init_db

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import sessionmaker


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    session_factory: sessionmaker | None = None,
) -> Flask:
    settings = settings or get_settings()
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=settings.database_url,
        JWT_SECRET=settings.jwt_secret,
        JWT_EXPIRES_MINUTES=settings.jwt_expires_minutes,
        TICK_SECRET=settings.tick_secret,
        ADMIN_SECRET=settings.admin_secret,
        DEFAULT_BATCH_SIZE=settings.default_batch_size,
        DEFAULT_BATCH_WINDOW_MINUTES=settings.default_batch_window_minutes,
        DEFAULT_ESCALATE_HOURS_BEFORE=settings.default_escalate_hours_before,
    )

    init_db(app, engine=engine, session_factory=session_factory)
    register_error_handlers(app)
    _register_cors(app, settings.cors_origins)
    _register_blueprints(app)

    @app.get("/health")
    def health():  # type: ignore[no-untyped-def]
        return jsonify({"status": "ok"})

    return app


def _register_blueprints(app: Flask) -> None:
    from app.api.admin import bp as admin_bp
    from app.api.auth import bp as auth_bp
    from app.api.doctors import bp as doctors_bp
    from app.api.jobs import bp as jobs_bp
    from app.api.me import bp as me_bp
    from app.api.offers import bp as offers_bp
    from app.api.shifts import bp as shifts_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(shifts_bp)
    app.register_blueprint(offers_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(admin_bp)


def _register_cors(app: Flask, origins_csv: str) -> None:
    allowed = {o.strip() for o in origins_csv.split(",") if o.strip()}

    @app.after_request
    def _add_cors_headers(resp):  # type: ignore[no-untyped-def]
        origin = request.headers.get("Origin")
        if origin and origin in allowed:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PATCH, DELETE, OPTIONS"
            )
        return resp
