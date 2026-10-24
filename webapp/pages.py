from __future__ import annotations

import hmac

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

pages = Blueprint("pages", __name__)


@pages.route("/")
def index():
    return render_template("index.html")


@pages.route("/login", methods=["GET", "POST"])
def login():
    password = current_app.config["APP_PASSWORD"]
    if not password:
        return redirect(url_for("pages.index"))

    error = None
    if request.method == "POST":
        submitted = request.form.get("password", "")
        if hmac.compare_digest(submitted.encode(), password.encode()):
            session.clear()
            session.permanent = True
            session["authenticated"] = True
            return redirect(url_for("pages.index"))
        error = "Wrong password."
    return render_template("login.html", error=error)


@pages.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("pages.login"))
