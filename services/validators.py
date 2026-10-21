"""Backend validation for every user-supplied value."""
import re
from datetime import date, timedelta
from config import (CYCLE_MIN, CYCLE_MAX, PERIOD_MIN, PERIOD_MAX, NOTES_MAX, MOODS, SYMPTOMS)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_iso(v):
    if not isinstance(v, str) or not DATE_RE.match(v.strip()):
        return None
    try:
        return date.fromisoformat(v.strip())
    except ValueError:
        return None


def _notes(data, errors):
    n = data.get("notes")
    if n is None:
        return None
    if not isinstance(n, str):
        errors["notes"] = "Notes must be text."
        return None
    n = n.strip()
    if len(n) > NOTES_MAX:
        errors["notes"] = f"Notes can be at most {NOTES_MAX} characters."
    return n or None


def _int(v):
    if isinstance(v, bool):
        raise ValueError
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r"\d{1,4}", v.strip()):
        return int(v.strip())
    raise ValueError


def validate_period(data, today):
    errors, e = {}, None
    raw_s = data.get("start_date")
    s = parse_iso(raw_s)
    if not raw_s:
        errors["start_date"] = "Start date is required."
    elif s is None:
        errors["start_date"] = "Enter a valid date (YYYY-MM-DD)."
    elif s > today:
        errors["start_date"] = "Start date can't be in the future."
    elif s < today - timedelta(days=365 * 100):
        errors["start_date"] = "Start date is too far in the past."
    raw_e = data.get("end_date")
    if raw_e not in (None, ""):
        e = parse_iso(raw_e)
        if e is None:
            errors["end_date"] = "Enter a valid date (YYYY-MM-DD)."
        elif s and e < s:
            errors["end_date"] = "End date can't be before the start date."
        elif e > today:
            errors["end_date"] = "End date can't be in the future. Leave it blank if your period is ongoing."
        elif s and (e - s).days + 1 > PERIOD_MAX:
            errors["end_date"] = f"A period can be at most {PERIOD_MAX} days. Please check the dates."
    notes = _notes(data, errors)
    clean = {"start_date": s.isoformat() if s else None, "end_date": e.isoformat() if e else None, "notes": notes}
    return clean, errors


def validate_symptom(data, today):
    errors = {}
    raw_d = data.get("date")
    d = parse_iso(raw_d)
    if not raw_d:
        errors["date"] = "Date is required."
    elif d is None:
        errors["date"] = "Enter a valid date (YYYY-MM-DD)."
    elif d > today:
        errors["date"] = "Date can't be in the future."
    elif d < today - timedelta(days=365 * 100):
        errors["date"] = "Date is too far in the past."
    mood = data.get("mood")
    if mood in ("", None):
        mood = None
    elif mood not in MOODS:
        errors["mood"] = "Choose one of the listed moods."
    syms = data.get("symptoms", [])
    if syms is None:
        syms = []
    if not isinstance(syms, list) or any(s not in SYMPTOMS for s in syms if isinstance(s, str)) \
            or any(not isinstance(s, str) for s in syms):
        errors["symptoms"] = "Choose symptoms from the list."
        syms = []
    syms = list(dict.fromkeys(syms))
    sev = data.get("severity")
    try:
        sev = _int(sev)
        if sev is not None and sev not in (1, 2, 3):
            raise ValueError
    except ValueError:
        errors["severity"] = "Severity must be 1 (mild), 2 (moderate) or 3 (strong)."
        sev = None
    notes = _notes(data, errors)
    if not errors and not (mood or syms or notes):
        errors["form"] = "Add a mood, at least one symptom, or a note."
    if sev and not syms and "symptoms" not in errors and not errors:
        sev = None  # severity only applies to symptoms
    return {"date": d.isoformat() if d else None, "mood": mood, "symptoms": syms,
            "severity": sev, "notes": notes}, errors


def validate_prefs(data):
    """Partial validation: only keys present in `data` are returned."""
    clean, errors = {}, {}
    for key, lo, hi, label in (("typical_cycle_length", CYCLE_MIN, CYCLE_MAX, "Cycle length"),
                               ("typical_period_length", PERIOD_MIN, PERIOD_MAX, "Period length")):
        if key in data:
            try:
                v = _int(data[key])
                if v is not None and not lo <= v <= hi:
                    raise ValueError
                clean[key] = v
            except ValueError:
                errors[key] = f"{label} must be a whole number from {lo} to {hi} days, or left blank."
    if "reminders_enabled" in data:
        v = data["reminders_enabled"]
        if isinstance(v, bool):
            clean["reminders_enabled"] = v
        elif isinstance(v, str) and v.lower() in ("1", "true", "on", "0", "false", "off", ""):
            clean["reminders_enabled"] = v.lower() in ("1", "true", "on")
        else:
            errors["reminders_enabled"] = "Must be true or false."
    return clean, errors


def validate_name(name):
    name = (name or "").strip() if isinstance(name, str) else ""
    if not name:
        return None, "Display name is required."
    if len(name) > 60:
        return None, "Display name can be at most 60 characters."
    return name, None


def validate_signup(form):
    errors = {}
    name, err = validate_name(form.get("display_name"))
    if err:
        errors["display_name"] = err
    email = (form.get("email") or "").strip().lower()
    if not email:
        errors["email"] = "Email is required."
    elif len(email) > 254 or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    pw, pw2 = form.get("password") or "", form.get("confirm_password") or ""
    if len(pw) < 8:
        errors["password"] = "Password must be at least 8 characters."
    elif len(pw) > 128:
        errors["password"] = "Password is too long (max 128 characters)."
    elif not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        errors["password"] = "Password must include at least one letter and one number."
    if "password" not in errors and pw != pw2:
        errors["confirm_password"] = "Passwords do not match."
    return {"display_name": name, "email": email, "password": pw}, errors
