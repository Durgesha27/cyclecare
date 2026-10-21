import json
import sqlite3
from flask import Blueprint, render_template, request, g, jsonify
from models.models import query, execute, symptom_json
from services.security import login_required
from services.validators import validate_symptom, parse_iso
from services.cycle_calculator import today_date

bp = Blueprint("symptoms", __name__)


def _owned(sid):
    return query("SELECT * FROM symptom_entries WHERE id=? AND user_id=?", (sid, g.user["id"]), one=True)


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _filtered(args):
    sql, params = "SELECT * FROM symptom_entries WHERE user_id=?", [g.user["id"]]
    bad = None
    for key, op in (("from", ">="), ("to", "<=")):
        v = args.get(key)
        if v:
            if parse_iso(v):
                sql += f" AND date {op} ?"
                params.append(v)
            else:
                bad = f"Invalid '{key}' date."
    return query(sql + " ORDER BY date DESC", params), bad


@bp.get("/symptoms")
@login_required
def symptoms_page():
    rows, bad = _filtered(request.args)
    prefill = request.args.get("date", "")
    return render_template("symptoms.html", entries=[symptom_json(r) for r in rows], filter_error=bad,
                           date_from=request.args.get("from", ""), date_to=request.args.get("to", ""),
                           prefill=prefill if parse_iso(prefill) else "")


@bp.get("/api/symptoms")
@login_required
def api_list():
    rows, bad = _filtered(request.args)
    if bad:
        return jsonify(error=bad), 400
    return jsonify(entries=[symptom_json(r) for r in rows])


@bp.post("/api/symptoms")
@login_required
def api_create():
    clean, errors = validate_symptom(_body(), today_date())
    if errors:
        return jsonify(error=errors.get("form", "Please fix the highlighted fields."), errors=errors), 422
    try:
        cur = execute("INSERT INTO symptom_entries(user_id,date,mood,symptoms,severity,notes) VALUES (?,?,?,?,?,?)",
                      (g.user["id"], clean["date"], clean["mood"], json.dumps(clean["symptoms"]),
                       clean["severity"], clean["notes"]))
    except sqlite3.IntegrityError:
        msg = "You already have a check-in for that date. Edit it instead."
        return jsonify(error=msg, errors={"date": msg}), 409
    return jsonify(entry=symptom_json(_owned(cur.lastrowid))), 201


@bp.get("/api/symptoms/<int:sid>")
@login_required
def api_get(sid):
    r = _owned(sid)
    if not r:
        return jsonify(error="Check-in not found."), 404
    return jsonify(entry=symptom_json(r))


@bp.put("/api/symptoms/<int:sid>")
@login_required
def api_update(sid):
    if not _owned(sid):
        return jsonify(error="Check-in not found."), 404
    clean, errors = validate_symptom(_body(), today_date())
    if errors:
        return jsonify(error=errors.get("form", "Please fix the highlighted fields."), errors=errors), 422
    try:
        execute("UPDATE symptom_entries SET date=?, mood=?, symptoms=?, severity=?, notes=?, "
                "updated_at=datetime('now') WHERE id=? AND user_id=?",
                (clean["date"], clean["mood"], json.dumps(clean["symptoms"]), clean["severity"],
                 clean["notes"], sid, g.user["id"]))
    except sqlite3.IntegrityError:
        msg = "You already have a check-in for that date."
        return jsonify(error=msg, errors={"date": msg}), 409
    return jsonify(entry=symptom_json(_owned(sid)))


@bp.delete("/api/symptoms/<int:sid>")
@login_required
def api_delete(sid):
    if not _owned(sid):
        return jsonify(error="Check-in not found."), 404
    execute("DELETE FROM symptom_entries WHERE id=? AND user_id=?", (sid, g.user["id"]))
    return jsonify(deleted=sid)
