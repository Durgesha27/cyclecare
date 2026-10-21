# CycleCare

A private, lightweight menstrual cycle tracker built with Flask and SQLite. Log periods and daily symptoms, see cycle estimates on a calendar, and review trends — with your data kept in a local database you control.

> **Disclaimer:** CycleCare is for personal tracking only. All predictions are estimates based on your own logged data and are **not medical advice** or a method of contraception. Talk to a healthcare professional about any health concerns.

## Features

- **Accounts** – sign up, log in/out, short onboarding flow, 14-day sessions
- **Period logging** – start/end dates, ongoing periods, notes; full history with edit and delete
- **Symptom & mood check-ins** – one entry per day with mood, symptoms, severity (mild/moderate/strong) and notes
- **Dashboard** – current cycle status, estimated next period, and an in-app reminder window
- **Calendar** – monthly view of logged and predicted days
- **Insights** – cycle and period length trends (charts rendered with Chart.js)
- **Settings** – typical cycle/period length, reminders, JSON data export, and full account deletion
- **Responsive UI** – works on desktop and mobile

## How estimates work

- Cycle length = days between consecutive period **start** dates.
- Intervals outside 15–90 days are flagged as suspicious and excluded.
- The estimate is the **median** of the most recent valid intervals (up to 6), which is robust to outliers. With only one interval it is marked as "limited"; with none, your "typical cycle length" setting is used if provided.
- Future and duplicate start dates are ignored. Period duration is never confused with cycle length.

See `services/cycle_calculator.py` for details.

## Tech stack

- Python 3 · Flask 3.1 · stdlib `sqlite3`
- `python-dotenv` for configuration
- Vanilla JavaScript and CSS; Chart.js loaded from jsDelivr on the Insights page

## Getting started

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) configure the environment
cp .env.example .env             # then edit SECRET_KEY etc.

# 4. Run the app
python app.py
```

Open <http://127.0.0.1:5000>. The SQLite database and tables are created automatically on first run in `instance/`.

If `SECRET_KEY` is not set, a random key is generated and stored in `instance/secret_key` so sessions survive restarts.

## Configuration

Set via environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | auto-generated & persisted | Flask session signing key. Set a long random string in production. |
| `DATABASE_PATH` | `instance/cyclecare.db` | Location of the SQLite file. |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` when served over HTTPS. |
| `LOGIN_MAX_ATTEMPTS` | `5` | Failed logins allowed per window. |
| `LOGIN_WINDOW_SECONDS` | `900` | Rate-limit window length. |
| `FLASK_DEBUG` | `0` | Set to `1` for debug mode (development only). |

Validation limits (cycle/period length bounds, note length, mood and symptom options) live in `config.py`.

## Running tests

```bash
python -m pytest tests
# or, using the standard library runner:
python -m unittest discover tests
```

Tests cover authentication, access control, periods, symptoms, settings and the cycle calculator.

## Project structure

```
cyclecare/
├── app.py                  # Application factory, security headers, error handlers
├── config.py               # Config and validation limits
├── models/models.py        # SQLite schema and query helpers
├── routes/                 # Blueprints: auth, dashboard, periods, symptoms, insights, settings
├── services/
│   ├── cycle_calculator.py # Pure-Python cycle analysis
│   ├── security.py         # CSRF, login_required, safe redirects
│   └── validators.py       # Input validation
├── templates/              # Jinja2 templates
├── static/                 # CSS and JavaScript
├── tests/                  # Test suite
├── instance/               # Local database and secret key (git-ignored)
├── requirements.txt
└── .env.example
```

## Pages and API

| Page | Path |
|---|---|
| Home / About / Privacy | `/`, `/about`, `/privacy` |
| Sign up / Log in / Onboarding | `/signup`, `/login`, `/onboarding` |
| Dashboard, Calendar, Insights | `/dashboard`, `/calendar`, `/insights` |
| Log period, History | `/log-period`, `/history` |
| Symptoms | `/symptoms` |
| Settings, Export | `/settings`, `/settings/export` |

JSON API (login required; unsafe methods need the `X-CSRF-Token` header):

| Method | Endpoint | Purpose |
|---|---|---|
| GET / POST | `/api/periods` | List / create periods |
| GET / PUT / DELETE | `/api/periods/<id>` | Read / update / delete a period |
| GET / POST | `/api/symptoms` | List / create check-ins |
| GET / PUT / DELETE | `/api/symptoms/<id>` | Read / update / delete a check-in |
| GET / PUT | `/api/preferences` | Read / update preferences |
| GET | `/api/calendar` | Calendar data |
| GET | `/api/insights` | Insight data |

## Security & privacy

- Passwords are hashed; sessions use `HttpOnly` and `SameSite=Lax` cookies
- CSRF token required on all state-changing requests
- Login rate limiting; safe-redirect validation
- Per-user data isolation, with access-control tests
- Security headers (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`) and `no-store` caching for signed-in pages
- Request size capped at 64 KB
- Users can export all their data as JSON or permanently delete their account

## Production notes

- Set a strong `SECRET_KEY` and `SESSION_COOKIE_SECURE=1` behind HTTPS
- Run with a WSGI server (e.g. `gunicorn app:create_app()`) instead of the Flask dev server
- Back up the `instance/` directory regularly
- Keep `FLASK_DEBUG` off
