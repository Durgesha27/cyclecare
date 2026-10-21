"""Application configuration. Limits here are used by validation and calculations."""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Configurable validation limits
CYCLE_MIN, CYCLE_MAX = 15, 90      # plausible days between period starts
PERIOD_MIN, PERIOD_MAX = 1, 15     # plausible period duration in days
NOTES_MAX = 500

MOODS = ["Happy", "Calm", "Low", "Irritable", "Anxious", "Other"]
SYMPTOMS = ["Cramps", "Headache", "Fatigue", "Bloating", "Back discomfort", "Tenderness", "Other"]
SEVERITY_LABELS = {1: "Mild", 2: "Moderate", 3: "Strong"}


class Config:
    DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "instance", "cyclecare.db"))
    SECRET_KEY = os.environ.get("SECRET_KEY")  # falls back to a persisted random key (see app.py)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    MAX_CONTENT_LENGTH = 64 * 1024
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", 5))
    LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", 900))
    REMINDER_DAYS = 3  # in-app dashboard reminder window
