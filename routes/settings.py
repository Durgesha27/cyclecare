import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, g, jsonify, redirect, url_for, session, Response
from werkzeug.security import check_password_hash
from models.models import query, execute, get_prefs, save_prefs, period_json, symptom_json
from services.security import login_required
from services.validators import validate_prefs, validate_name

bp = Blueprint("settings", __name__)


@bp.get("/settings")
@login_required
def settings_page():
    return render_template("settings.html", prefs=get_prefs(g.user["id"]), errors={}, form_error=None)


@bp.post("/settings/profile")
@login_required
def update_profile():
    name, err = validate_name(request.form.get("display_name"))
    if err:
        return render_template("settings.html", prefs=get_prefs(g.user["id"]), errors={"display_name": err},
                               form_error=None), 400
    execute("UPDATE users SET display_name=? WHERE id=?", (name, g.user["id"]))
    return redirect(url_for("settings.settings_page", notice="settings_saved"))


@bp.post("/settings/preferences")
@login_required
def update_preferences():
    data = {"typical_cycle_length": request.form.get("typical_cycle_length", ""),
            "typical_period_length": request.form.get("typical_period_length", ""),
            "reminders_enabled": "1" if request.form.get("reminders_enabled") else "0"}
    clean, errors = validate_prefs(data)
    if errors:
        return render_template("settings.html", prefs={**get_prefs(g.user["id"]), **data}, errors=errors,
                               form_error=None), 400
    save_prefs(g.user["id"], clean)
    return redirect(url_for("settings.settings_page", notice="settings_saved"))


@bp.get("/settings/export")
@login_required
def export():
    uid = g.user["id"]
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "note": "Your CycleCare data. Estimates are not medical advice.",
        "user": {"display_name": g.user["display_name"], "email": g.user["email"]},
        "preferences": get_prefs(uid),
        "periods": [period_json(r) for r in query("SELECT * FROM period_records WHERE user_id=? ORDER BY start_date", (uid,))],
        "symptoms": [symptom_json(r) for r in query("SELECT * FROM symptom_entries WHERE user_id=? ORDER BY date", (uid,))],
    }
    return Response(json.dumps(payload, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=cyclecare-export.json"})


@bp.post("/settings/delete")
@login_required
def delete_account():
    user = query("SELECT * FROM users WHERE id=?", (g.user["id"],), one=True)
    err = None
    if (request.form.get("confirm_text") or "").strip() != "DELETE":
        err = "Type DELETE to confirm."
    elif not check_password_hash(user["password_hash"], request.form.get("password") or ""):
        err = "Password is incorrect."
    if err:
        return render_template("settings.html", prefs=get_prefs(user["id"]), errors={}, form_error=err), 400
    execute("DELETE FROM users WHERE id=?", (user["id"],))  # cascades to all related records
    session.clear()
    return redirect(url_for("dashboard.index", notice="account_deleted"))


@bp.get("/api/preferences")
@login_required
def api_get_prefs():
    return jsonify(preferences=get_prefs(g.user["id"]))


@bp.put("/api/preferences")
@login_required
def api_put_prefs():
    data = request.get_json(silent=True)
    clean, errors = validate_prefs(data if isinstance(data, dict) else {})
    if errors:
        return jsonify(error="Please fix the highlighted fields.", errors=errors), 422
    return jsonify(preferences=save_prefs(g.user["id"], clean))
