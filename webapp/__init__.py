"""Diabetes coach web app."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, request, session, url_for

from . import db

PUBLIC_ENDPOINTS = {"pages.login", "static"}


def create_app() -> Flask:
    # Prefer project .env over any empty/stale shell exports of the same keys.
    load_dotenv(db.PROJECT_ROOT / ".env", override=True)

    app = Flask(__name__)
    # Without SECRET_KEY, a random key is used and logins reset whenever the app restarts.
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config.update(
        APP_PASSWORD=os.environ.get("APP_PASSWORD"),
        PERMANENT_SESSION_LIFETIME=timedelta(days=90),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SECURE_COOKIES") == "1",
        MAX_CONTENT_LENGTH=200 * 1024 * 1024,
    )

    conn = db.connect()
    db.migrate(conn)
    conn.close()

    @app.before_request
    def open_db() -> None:
        g.db = db.connect()

    @app.teardown_request
    def close_db(_exc: BaseException | None) -> None:
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.before_request
    def require_login():
        # Login is only enforced when APP_PASSWORD is set; always set it on a public server.
        if not app.config["APP_PASSWORD"] or request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if session.get("authenticated"):
            return None
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not logged in"}), 401
        return redirect(url_for("pages.login"))

    @app.context_processor
    def asset_helpers():
        # The version query string changes whenever the file changes, so browsers
        # (and the iPhone home-screen app) can't keep serving an outdated copy.
        def asset_url(filename: str) -> str:
            path = Path(app.static_folder) / filename
            return url_for("static", filename=filename, v=int(path.stat().st_mtime))

        return {"asset_url": asset_url, "auth_enabled": bool(app.config["APP_PASSWORD"])}

    from .api import api
    from .imports import imports
    from .pages import pages

    app.register_blueprint(pages)
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(imports, url_prefix="/api/imports")
    return app
