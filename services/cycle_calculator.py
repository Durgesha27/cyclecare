"""Cycle calculations (pure Python, no Flask/DB dependency).

Method (documented):
* A *cycle length* is the number of days between two consecutive recorded period START dates.
* Intervals outside CYCLE_MIN..CYCLE_MAX are flagged suspicious and excluded from estimates.
* The estimated cycle length is the MEDIAN of the most recent valid intervals (robust to outliers).
  With a single valid interval the estimate is flagged "limited". With none, the user's own
  "typical cycle length" preference is used if set; otherwise no estimate is produced.
* Future start dates and duplicate start dates are ignored. Open (no end date) records are valid.
* Period duration (end - start + 1) is never mixed up with cycle length.
All future dates are ESTIMATES only.
"""
import statistics
from datetime import date, timedelta
from config import CYCLE_MIN, CYCLE_MAX

RECENT_INTERVALS = 6


def today_date():
    return date.today()


def _d(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def _median_int(values):
    return int(statistics.median(values) + 0.5)


def analyze(periods, today=None, typical_cycle=None, typical_period=None):
    today = today or today_date()
    starts, durations = [], []
    seen = set()
    duplicates = incomplete = ignored_future = 0
    parsed = []
    for p in periods or []:
        try:
            s = _d(p["start_date"])
            e = _d(p["end_date"]) if p.get("end_date") else None
        except (ValueError, TypeError, KeyError):
            continue
        parsed.append((s, e))
    for s, e in sorted(parsed, key=lambda x: x[0]):
        if s > today:
            ignored_future += 1
            continue
        if s in seen:
            duplicates += 1
            continue
        seen.add(s)
        starts.append(s)
        if e is None:
            incomplete += 1
        elif e >= s:
            durations.append({"start_date": s.isoformat(), "days": (e - s).days + 1})

    intervals, interval_before = [], {}
    for a, b in zip(starts, starts[1:]):
        days = (b - a).days
        valid = CYCLE_MIN <= days <= CYCLE_MAX
        item = {"from_date": a.isoformat(), "to_date": b.isoformat(), "days": days, "valid": valid}
        intervals.append(item)
        interval_before[b.isoformat()] = {"days": days, "valid": valid}
    valid_days = [i["days"] for i in intervals if i["valid"]]

    est, source, confidence = None, None, None
    if valid_days:
        est = _median_int(valid_days[-RECENT_INTERVALS:])
        source = "history"
        confidence = "good" if len(valid_days) >= 3 else "limited"
    elif typical_cycle:
        est, source, confidence = int(typical_cycle), "preference", "limited"

    period_len = None
    if durations:
        period_len = _median_int([d["days"] for d in durations][-RECENT_INTERVALS:])
    elif typical_period:
        period_len = int(typical_period)

    latest = starts[-1] if starts else None
    next_start = latest + timedelta(days=est) if (latest and est) else None
    cycle_day = None
    if latest:
        cd = (today - latest).days + 1
        if 1 <= cd <= CYCLE_MAX:
            cycle_day = cd
    predicted = []
    if next_start:
        predicted = [(next_start + timedelta(days=i)).isoformat() for i in range(period_len or 1)]
    variation = (max(valid_days) - min(valid_days)) if len(valid_days) >= 2 else None
    regularity = None
    if len(valid_days) >= 3:
        regularity = "steady" if variation <= 7 else "variable"

    status = "no_data" if not starts else ("ok" if est else "insufficient")
    return {
        "status": status,
        "record_count": len(starts),
        "latest_start": latest.isoformat() if latest else None,
        "intervals": intervals,
        "interval_before": interval_before,
        "valid_intervals": valid_days,
        "estimated_cycle_length": est,
        "cycle_length_source": source,
        "confidence": confidence,
        "next_period_start": next_start.isoformat() if next_start else None,
        "days_until": (next_start - today).days if next_start else None,
        "cycle_day": cycle_day,
        "estimated_period_length": period_len,
        "predicted_dates": predicted,
        "durations": durations,
        "variation": variation,
        "regularity": regularity,
        "duplicates": duplicates,
        "incomplete": incomplete,
        "ignored_future": ignored_future,
        "suspicious": sum(1 for i in intervals if not i["valid"]),
    }
