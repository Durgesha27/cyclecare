import calendar as pycal
import math
from datetime import date, timedelta
from flask import Blueprint, render_template, request, g, jsonify, current_app
from config import PERIOD_MAX
from models.models import query, get_prefs, get_analysis, period_json, symptom_json
from services.security import login_required
from services.cycle_calculator import today_date

bp = Blueprint("dashboard", __name__)


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _period_days(uid, first, last, today):
    """ISO dates in [first, last] that fall inside a recorded period (ongoing ones capped)."""
    days = set()
    rows = query("SELECT start_date, end_date FROM period_records WHERE user_id=? AND start_date<=? "
                 "AND COALESCE(end_date, start_date) >= ?",
                 (uid, last.isoformat(), (first - timedelta(days=PERIOD_MAX)).isoformat()))
    for r in rows:
        s = date.fromisoformat(r["start_date"])
        e = date.fromisoformat(r["end_date"]) if r["end_date"] else min(today, s + timedelta(days=PERIOD_MAX - 1))
        for i in range((max(e, s) - s).days + 1):
            days.add((s + timedelta(days=i)).isoformat())
    return days


def _week_strip(uid, a, today):
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    recorded = _period_days(uid, monday, sunday, today)
    predicted = set(a["predicted_dates"])
    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        iso = d.isoformat()
        kind = "period" if iso in recorded else ("predicted" if iso in predicted else "")
        label = {"period": "recorded period", "predicted": "estimated period, not confirmed"}.get(kind, "")
        out.append({"name": WEEKDAYS[i], "num": d.day, "kind": kind, "today": d == today, "label": label})
    return out


def _ring(a):
    """Geometry for the cycle ring. Only built when cycle length and cycle day are both known."""
    L, day = a["estimated_cycle_length"], a["cycle_day"]
    if a["status"] != "ok" or not L or not day:
        return None
    P = min(a["estimated_period_length"] or 0, L - 1)
    pre = max(min(3, L - P - 1), 0)
    parts = [("ring-period", P), ("ring-mid", L - P - pre), ("ring-pre", pre)]
    R = 90
    C = 2 * math.pi * R
    segs, start = [], 0
    for cls, n in parts:
        if n > 0:
            segs.append({"cls": cls, "dash": round(max(C * n / L - 3, 1), 2),
                         "gap": round(C, 2), "offset": round(-C * start / L, 2)})
        start += n
    ang = 2 * math.pi * (min(day, L) - 0.5) / L - math.pi / 2
    return {"segs": segs, "mx": round(110 + R * math.cos(ang), 1), "my": round(110 + R * math.sin(ang), 1),
            "day": day, "length": L, "late": day > L, "has_period_seg": P > 0}


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/privacy")
def privacy():
    return render_template("info.html", page="privacy")


@bp.get("/about")
def about():
    return render_template("info.html", page="about")


@bp.get("/dashboard")
@login_required
def home():
    uid = g.user["id"]
    a, prefs = get_analysis(uid), get_prefs(uid)
    periods = [period_json(r) for r in query(
        "SELECT * FROM period_records WHERE user_id=? ORDER BY start_date DESC LIMIT 4", (uid,))]
    symptoms = [symptom_json(r) for r in query(
        "SELECT * FROM symptom_entries WHERE user_id=? ORDER BY date DESC LIMIT 4", (uid,))]
    today = today_date()
    today_checkin = query("SELECT * FROM symptom_entries WHERE user_id=? AND date=?",
                          (uid, today.isoformat()), one=True)
    today_checkin = symptom_json(today_checkin) if today_checkin else None
    reminder = (prefs["reminders_enabled"] and a["days_until"] is not None
                and 0 <= a["days_until"] <= current_app.config["REMINDER_DAYS"])
    return render_template("dashboard.html", a=a, periods=periods, symptoms=symptoms,
                           prefs=prefs, reminder=reminder, today=today,
                           week=_week_strip(uid, a, today), ring=_ring(a), checkin=today_checkin)


@bp.get("/calendar")
@login_required
def calendar():
    return render_template("calendar.html")


@bp.get("/api/calendar")
@login_required
def api_calendar():
    today = today_date()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        first = date(year, month, 1)
    except (ValueError, OverflowError):
        return jsonify(error="Invalid year or month."), 400
    last = date(year, month, pycal.monthrange(year, month)[1])
    uid = g.user["id"]
    rows = query("SELECT * FROM period_records WHERE user_id=? AND start_date<=? AND "
                 "COALESCE(end_date, start_date) >= ? ORDER BY start_date",
                 (uid, last.isoformat(), (first - timedelta(days=PERIOD_MAX)).isoformat()))
    periods = []
    for r in rows:
        s = date.fromisoformat(r["start_date"])
        e = date.fromisoformat(r["end_date"]) if r["end_date"] else min(today, s + timedelta(days=PERIOD_MAX - 1))
        e = max(e, s)
        days = [(s + timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]
        if days[-1] < first.isoformat() or days[0] > last.isoformat():
            continue
        periods.append({**period_json(r), "days": days})
    sym_dates = [r["date"] for r in query(
        "SELECT date FROM symptom_entries WHERE user_id=? AND date BETWEEN ? AND ?",
        (uid, first.isoformat(), last.isoformat()))]
    a = get_analysis(uid)
    return jsonify(year=year, month=month, today=today.isoformat(), periods=periods,
                   predicted=a["predicted_dates"], symptom_dates=sym_dates,
                   estimate_source=a["cycle_length_source"])
