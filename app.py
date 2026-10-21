"""CycleCare — Flask application factory."""
import os
import secrets
from flask import Flask, g, session, request, jsonify, render_template
from config import Config, MOODS, SYMPTOMS, SEVERITY_LABELS
from models.models import close_db, init_db, query
from services.security import csrf_token, check_csrf, is_api
from services.cycle_calculator import today_date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # optional dependency
    pass

NOTICES = {
    "period_saved": "Period saved.", "period_deleted": "Period deleted.",
    "symptom_saved": "Check-in saved.", "symptom_deleted": "Check-in deleted.",
    "settings_saved": "Settings saved.", "logged_out": "You have been logged out.",
    "account_deleted": "Your account and all of its data have been deleted.",
}


def _secret_key(app):
    if app.config.get("SECRET_KEY"):
        return app.config["SECRET_KEY"]
    path = os.path.join(os.path.dirname(os.path.abspath(app.config["DATABASE"])), "secret_key")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(key)
    os.chmod(path, 0o600)
    return key


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)
    app.config["SECRET_KEY"] = _secret_key(app)

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from routes import auth, dashboard, periods, symptoms, insights, settings
    for module in (auth, dashboard, periods, symptoms, insights, settings):
        app.register_blueprint(module.bp)

    @app.before_request
    def _load_user():
        uid = session.get("uid")
        g.user = query("SELECT id, display_name, email, onboarded FROM users WHERE id=?", (uid,), one=True) if uid else None
        if uid and g.user is None:
            session.pop("uid", None)

    app.before_request(check_csrf)

    @app.context_processor
    def _inject():
        notice = NOTICES.get(request.args.get("notice", ""))
        return dict(csrf_token=csrf_token, notice=notice, today_iso=today_date().isoformat(),
                    MOODS=MOODS, SYMPTOMS=SYMPTOMS, SEVERITY_LABELS=SEVERITY_LABELS)

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'")
        if g.get("user"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def _err(code, template, msg):
        if is_api():
            return jsonify(error=msg), code
        return render_template(template, message=msg), code

    @app.errorhandler(403)
    def _403(_e):
        return _err(403, "403.html", "You don't have permission to view this page.")

    @app.errorhandler(404)
    def _404(_e):
        return _err(404, "404.html", "We couldn't find that page.")

    @app.errorhandler(413)
    def _413(_e):
        return _err(413, "500.html", "That request was too large.")

    @app.errorhandler(500)
    def _500(_e):
        return _err(500, "500.html", "Something went wrong on our side. Please try again.")

    return app


if __name__ == "__main__":
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1")
