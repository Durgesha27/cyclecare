"""CSRF protection, authentication helpers and safe redirects."""
import secrets
from functools import wraps
from urllib.parse import urlparse
from flask import session, request, redirect, url_for, g, jsonify, render_template


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def is_api():
    return request.path.startswith("/api/")


def check_csrf():
    """Run before every request: unsafe methods must carry a valid token."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(sent, expected):
            if is_api():
                return jsonify(error="Invalid or missing security token. Refresh the page and try again."), 403
            return render_template("403.html", message="Your session security token was missing or expired. "
                                                       "Please go back, refresh the page and try again."), 403
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            if is_api():
                return jsonify(error="Authentication required."), 401
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*a, **kw)
    return wrapped


def safe_next(target):
    if not target:
        return None
    p = urlparse(target)
    if p.scheme or p.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target
