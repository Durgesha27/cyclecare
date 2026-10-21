from flask import Blueprint, render_template, g, jsonify
from models.models import get_analysis
from services.security import login_required

bp = Blueprint("insights", __name__)


def _payload(a):
    needs = None
    if a["record_count"] < 2:
        needs = "Record at least two period start dates to see your first cycle interval."
    elif len(a["valid_intervals"]) < 3:
        needs = "Record a few more periods to see variation and a steadier typical cycle length."
    return {
        "recorded_periods": a["record_count"],
        "typical_cycle_length": a["estimated_cycle_length"] if a["cycle_length_source"] == "history" else None,
        "variation": a["variation"], "regularity": a["regularity"], "confidence": a["confidence"],
        "cycle_lengths": a["intervals"], "durations": a["durations"],
        "suspicious": a["suspicious"], "needs": needs,
    }


@bp.get("/insights")
@login_required
def insights_page():
    a = get_analysis(g.user["id"])
    return render_template("insights.html", a=a, data=_payload(a))


@bp.get("/api/insights")
@login_required
def api_insights():
    return jsonify(_payload(get_analysis(g.user["id"])))
