"""Database layer (stdlib sqlite3): schema, connection handling and small query helpers."""
import json
import sqlite3
from flask import current_app, g
from services.cycle_calculator import analyze, today_date

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  display_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  onboarded INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS period_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  start_date TEXT NOT NULL,
  end_date TEXT,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK (end_date IS NULL OR end_date >= start_date),
  UNIQUE (user_id, start_date)
);
CREATE INDEX IF NOT EXISTS ix_period_user_start ON period_records(user_id, start_date);
CREATE TABLE IF NOT EXISTS symptom_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  mood TEXT,
  symptoms TEXT NOT NULL DEFAULT '[]',
  severity INTEGER CHECK (severity IS NULL OR severity BETWEEN 1 AND 3),
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (user_id, date)
);
CREATE INDEX IF NOT EXISTS ix_symptom_user_date ON symptom_entries(user_id, date);
CREATE TABLE IF NOT EXISTS cycle_preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  typical_cycle_length INTEGER,
  typical_period_length INTEGER,
  reminders_enabled INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL,
  ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_login_key ON login_attempts(key, ts);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if missing. Never drops or deletes existing data."""
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def query(sql, args=(), one=False):
    rows = [dict(r) for r in get_db().execute(sql, args).fetchall()]
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    db = get_db()
    try:
        cur = db.execute(sql, args)
        db.commit()
        return cur
    except sqlite3.Error:
        db.rollback()
        raise


# ---- Preferences -------------------------------------------------------
def get_prefs(uid):
    row = query("SELECT * FROM cycle_preferences WHERE user_id=?", (uid,), one=True)
    if row is None:
        execute("INSERT OR IGNORE INTO cycle_preferences(user_id) VALUES (?)", (uid,))
        row = query("SELECT * FROM cycle_preferences WHERE user_id=?", (uid,), one=True)
    row["reminders_enabled"] = bool(row["reminders_enabled"])
    return row


def save_prefs(uid, clean):
    merged = {**get_prefs(uid), **clean}
    execute(
        "UPDATE cycle_preferences SET typical_cycle_length=?, typical_period_length=?, "
        "reminders_enabled=?, updated_at=datetime('now') WHERE user_id=?",
        (merged["typical_cycle_length"], merged["typical_period_length"],
         1 if merged["reminders_enabled"] else 0, uid),
    )
    return get_prefs(uid)


# ---- Serialisers -------------------------------------------------------
def period_json(r):
    duration = None
    if r["end_date"]:
        from datetime import date
        duration = (date.fromisoformat(r["end_date"]) - date.fromisoformat(r["start_date"])).days + 1
    return {"id": r["id"], "start_date": r["start_date"], "end_date": r["end_date"],
            "notes": r["notes"], "ongoing": r["end_date"] is None, "duration_days": duration,
            "created_at": r["created_at"], "updated_at": r["updated_at"]}


def symptom_json(r):
    try:
        symptoms = json.loads(r["symptoms"] or "[]")
    except ValueError:
        symptoms = []
    return {"id": r["id"], "date": r["date"], "mood": r["mood"], "symptoms": symptoms,
            "severity": r["severity"], "notes": r["notes"],
            "created_at": r["created_at"], "updated_at": r["updated_at"]}


def get_analysis(uid):
    periods = query("SELECT start_date, end_date FROM period_records WHERE user_id=?", (uid,))
    prefs = get_prefs(uid)
    return analyze(periods, today_date(), prefs["typical_cycle_length"], prefs["typical_period_length"])
