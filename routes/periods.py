import sqlite3
from datetime import date, timedelta
from flask import Blueprint, render_template, request, g, jsonify, abort
from config import PERIOD_MAX
from models.models import query, execute, get_analysis, period_json
from services.security import login_required
from services.validators import validate_period, parse_iso
from services.cycle_calculator import today_date

bp = Blueprint("periods", __name__)


def _owned(pid):
    return query("SELECT * FROM period_records WHERE id=? AND user_id=?", (pid, g.user["id"]), one=True)


def _range(start, end):
    s = date.fromisoformat(start)
    return s, (date.fromisoformat(end) if end else s + timedelta(days=PERIOD_MAX - 1))


def _conflict(clean, exclude_id=None):
    """Return an error message if the record overlaps another of the user's records."""
    s, e = _range(clean["start_date"], clean["end_date"])
    for r in query("SELECT * FROM period_records WHERE user_id=?", (g.user["id"],)):
        if r["id"] == exclude_id:
            continue
        rs, re_ = _range(r["start_date"], r["end_date"])
        if r["start_date"] == clean["start_date"]:
            return "You already have a period recorded starting on that date. Edit it instead."
        if s <= re_ and rs <= e:
            if r["end_date"] is None:
                return ("This overlaps a period that is still marked ongoing "
                        f"(started {r['start_date']}). Add an end date to it first.")
            return f"These dates overlap another recorded period ({r['start_date']} to {r['end_date']})."
    return None


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@bp.get("/log-period")
@login_required
def log_period():
    record, prefill = None, request.args.get("date", "")
    if request.args.get("id"):
        try:
            record = _owned(int(request.args["id"]))
        except ValueError:
            record = None
        if not record:
            abort(404)
    return render_template("log_period.html", record=record,
                           prefill=prefill if parse_iso(prefill) else "")


@bp.get("/history")
@login_required
def history():
    uid = g.user["id"]
    order = "ASC" if request.args.get("order") == "asc" else "DESC"
    a = get_analysis(uid)
    rows = []
    for r in query(f"SELECT * FROM period_records WHERE user_id=? ORDER BY start_date {order}", (uid,)):
        rows.append({**period_json(r), "interval": a["interval_before"].get(r["start_date"])})
    return render_template("history.html", rows=rows, order=order.lower(), a=a)


@bp.get("/api/periods")
@login_required
def api_list():
    sql, args = "SELECT * FROM period_records WHERE user_id=?", [g.user["id"]]
    for key, op in (("from", ">="), ("to", "<=")):
        if request.args.get(key):
            if not parse_iso(request.args[key]):
                return jsonify(error=f"Invalid '{key}' date."), 400
            sql += f" AND start_date {op} ?"
            args.append(request.args[key])
    return jsonify(periods=[period_json(r) for r in query(sql + " ORDER BY start_date DESC", args)])


@bp.post("/api/periods")
@login_required
def api_create():
    clean, errors = validate_period(_body(), today_date())
    if errors:
        return jsonify(error="Please fix the highlighted fields.", errors=errors), 422
    msg = _conflict(clean)
    if msg:
        return jsonify(error=msg, errors={"start_date": msg}), 409
    try:
        cur = execute("INSERT INTO period_records(user_id,start_date,end_date,notes) VALUES (?,?,?,?)",
                      (g.user["id"], clean["start_date"], clean["end_date"], clean["notes"]))
    except sqlite3.IntegrityError:
        return jsonify(error="That period could not be saved."), 409
    return jsonify(period=period_json(_owned(cur.lastrowid))), 201


@bp.get("/api/periods/<int:pid>")
@login_required
def api_get(pid):
    r = _owned(pid)
    if not r:
        return jsonify(error="Period not found."), 404
    return jsonify(period=period_json(r))


@bp.put("/api/periods/<int:pid>")
@login_required
def api_update(pid):
    if not _owned(pid):
        return jsonify(error="Period not found."), 404
    clean, errors = validate_period(_body(), today_date())
    if errors:
        return jsonify(error="Please fix the highlighted fields.", errors=errors), 422
    msg = _conflict(clean, exclude_id=pid)
    if msg:
        return jsonify(error=msg, errors={"start_date": msg}), 409
    try:
        execute("UPDATE period_records SET start_date=?, end_date=?, notes=?, updated_at=datetime('now') "
                "WHERE id=? AND user_id=?",
                (clean["start_date"], clean["end_date"], clean["notes"], pid, g.user["id"]))
    except sqlite3.IntegrityError:
        return jsonify(error="That period could not be saved."), 409
    return jsonify(period=period_json(_owned(pid)))


@bp.delete("/api/periods/<int:pid>")
@login_required
def api_delete(pid):
    if not _owned(pid):
        return jsonify(error="Period not found."), 404
    execute("DELETE FROM period_records WHERE id=? AND user_id=?", (pid, g.user["id"]))
    return jsonify(deleted=pid)
