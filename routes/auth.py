import sqlite3
import time
from flask import Blueprint, render_template, request, redirect, url_for, session, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from models.models import get_db, query, execute, save_prefs
from services.security import login_required, safe_next
from services.validators import validate_signup, validate_prefs, validate_period
from services.cycle_calculator import today_date

bp = Blueprint("auth", __name__)
_DUMMY_HASH = generate_password_hash("not-a-real-password-1")  # equalises timing for unknown emails


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("dashboard.home"))
    form, errors = {}, {}
    if request.method == "POST":
        form = {k: request.form.get(k, "") for k in ("display_name", "email")}
        clean, errors = validate_signup(request.form)
        if not errors:
            db = get_db()
            try:
                with db:
                    cur = db.execute("INSERT INTO users(display_name,email,password_hash) VALUES (?,?,?)",
                                     (clean["display_name"], clean["email"], generate_password_hash(clean["password"])))
                    db.execute("INSERT INTO cycle_preferences(user_id) VALUES (?)", (cur.lastrowid,))
            except sqlite3.IntegrityError:
                errors["email"] = "An account with this email already exists. Try logging in."
            else:
                session.clear()
                session["uid"] = cur.lastrowid
                return redirect(url_for("auth.onboarding"))
    return render_template("signup.html", form=form, errors=errors), (400 if errors else 200)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard.home"))
    form, error, status = {}, None, 200
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()[:254]
        password = request.form.get("password") or ""
        form = {"email": email}
        key = f"{email}|{request.remote_addr}"
        now, cfg = time.time(), current_app.config
        execute("DELETE FROM login_attempts WHERE ts < ?", (now - cfg["LOGIN_WINDOW_SECONDS"],))
        attempts = query("SELECT COUNT(*) AS c FROM login_attempts WHERE key=?", (key,), one=True)["c"]
        if attempts >= cfg["LOGIN_MAX_ATTEMPTS"]:
            error, status = "Too many login attempts. Please wait a few minutes and try again.", 429
        else:
            user = query("SELECT * FROM users WHERE email=?", (email,), one=True)
            ok = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password) and user
            if not ok:
                execute("INSERT INTO login_attempts(key, ts) VALUES (?,?)", (key, now))
                error, status = "Incorrect email or password.", 401
            else:
                execute("DELETE FROM login_attempts WHERE key=?", (key,))
                session.clear()
                session["uid"] = user["id"]
                if not user["onboarded"]:
                    return redirect(url_for("auth.onboarding"))
                return redirect(safe_next(request.args.get("next")) or url_for("dashboard.home"))
    return render_template("login.html", form=form, error=error), status


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard.index", notice="logged_out"))


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    form, errors = {}, {}
    if request.method == "POST":
        form = {k: request.form.get(k, "") for k in ("last_period_start", "typical_cycle_length", "typical_period_length")}
        prefs, errors = validate_prefs({"typical_cycle_length": form["typical_cycle_length"],
                                        "typical_period_length": form["typical_period_length"]})
        period = None
        if form["last_period_start"].strip():
            period, perr = validate_period({"start_date": form["last_period_start"]}, today_date())
            if perr:
                errors["last_period_start"] = perr["start_date"]
        if not errors:
            uid = g.user["id"]
            save_prefs(uid, prefs)
            if period:
                execute("INSERT OR IGNORE INTO period_records(user_id,start_date) VALUES (?,?)",
                        (uid, period["start_date"]))
            execute("UPDATE users SET onboarded=1 WHERE id=?", (uid,))
            return redirect(url_for("dashboard.home"))
    return render_template("onboarding.html", form=form, errors=errors), (400 if errors else 200)


@bp.post("/onboarding/skip")
@login_required
def onboarding_skip():
    execute("UPDATE users SET onboarded=1 WHERE id=?", (g.user["id"],))
    return redirect(url_for("dashboard.home"))
