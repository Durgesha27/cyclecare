import sqlite3
from tests.base import AppTestCase, PW


class AuthTests(AppTestCase):
    def test_public_pages(self):
        for url in ("/", "/login", "/signup", "/privacy", "/about"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/nope").status_code, 404)

    def test_signup_success_hashes_password_and_goes_to_onboarding(self):
        r = self.signup()
        self.assertEqual(r.status_code, 302); self.assertTrue(r.location.endswith("/onboarding"))
        row = sqlite3.connect(self.path).execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotIn(PW, row); self.assertTrue(row.startswith(("scrypt:", "pbkdf2:")))
        self.assertEqual(self.client.get("/onboarding").status_code, 200)

    def test_signup_validation(self):
        self.assertEqual(self.signup(email="bad").status_code, 400)
        self.assertEqual(self.signup(pw="short1").status_code, 400)
        self.assertEqual(self.signup(pw="onlyletters").status_code, 400)
        self.assertEqual(self.signup(confirm="Different1").status_code, 400)
        self.assertEqual(self.signup(name="  ").status_code, 400)

    def test_form_data_kept_but_not_password(self):
        r = self.signup(email="bad", name="Keep Me")
        html = r.get_data(as_text=True)
        self.assertIn("Keep Me", html); self.assertNotIn(PW, html)

    def test_duplicate_email_case_insensitive(self):
        self.signup()
        r = self.signup(self.app.test_client(), email="ANA@example.com")
        self.assertEqual(r.status_code, 400); self.assertIn("already exists", r.get_data(as_text=True))

    def test_login_logout_flow(self):
        self.signup(); self.client.post("/logout", data={"csrf_token": self.token()})
        bad = self.client.post("/login", data={"csrf_token": self.token(), "email": "ana@example.com", "password": "wrong1234"})
        self.assertEqual(bad.status_code, 401)
        self.signup  # noqa
        self.client.post("/onboarding/skip", data={"csrf_token": self.token()})  # logged out -> redirect
        ok = self.client.post("/login", data={"csrf_token": self.token(), "email": "ana@example.com", "password": PW})
        self.assertEqual(ok.status_code, 302)
        self.assertTrue(ok.location.endswith("/onboarding"))  # not onboarded yet
        self.client.post("/onboarding/skip", data={"csrf_token": self.token()})
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        out = self.client.post("/logout", data={"csrf_token": self.token()})
        self.assertEqual(out.status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_logout_requires_post_and_csrf(self):
        c = self.new_user()
        self.assertEqual(c.get("/logout").status_code, 405)
        self.assertEqual(c.post("/logout").status_code, 403)
        self.assertEqual(c.get("/dashboard").status_code, 200)  # still logged in

    def test_protected_pages_redirect_to_login(self):
        for url in ("/dashboard", "/calendar", "/log-period", "/history", "/symptoms", "/insights", "/settings"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url); self.assertIn("/login", r.location)

    def test_open_redirect_blocked(self):
        self.signup(); c = self.client
        c.post("/onboarding/skip", data={"csrf_token": self.token()}); c.post("/logout", data={"csrf_token": self.token()})
        r = c.post("/login?next=https://evil.example", data={"csrf_token": self.token(), "email": "ana@example.com", "password": PW})
        self.assertTrue(r.location.endswith("/dashboard"))

    def test_login_rate_limit(self):
        self.signup(); self.client.post("/logout", data={"csrf_token": self.token()})
        codes = [self.client.post("/login", data={"csrf_token": self.token(), "email": "ana@example.com", "password": "nope12345"}).status_code for _ in range(6)]
        self.assertEqual(codes[:5], [401] * 5); self.assertEqual(codes[5], 429)
        good = self.client.post("/login", data={"csrf_token": self.token(), "email": "ana@example.com", "password": PW})
        self.assertEqual(good.status_code, 429)  # even correct password blocked while limited

    def test_signup_without_csrf_rejected(self):
        r = self.client.post("/signup", data={"display_name": "x", "email": "x@example.com", "password": PW, "confirm_password": PW})
        self.assertEqual(r.status_code, 403)

    def test_security_headers(self):
        h = self.client.get("/").headers
        self.assertEqual(h["X-Frame-Options"], "DENY"); self.assertIn("Content-Security-Policy", h)

    def test_onboarding_saves_prefs_and_period(self):
        self.signup()
        r = self.client.post("/onboarding", data={"csrf_token": self.token(), "last_period_start": self.day(10),
                                                  "typical_cycle_length": "30", "typical_period_length": "5"})
        self.assertEqual(r.status_code, 302)
        prefs = self.client.get("/api/preferences").get_json()["preferences"]
        self.assertEqual((prefs["typical_cycle_length"], prefs["typical_period_length"]), (30, 5))
        self.assertEqual(len(self.client.get("/api/periods").get_json()["periods"]), 1)

    def test_onboarding_validation(self):
        self.signup()
        r = self.client.post("/onboarding", data={"csrf_token": self.token(), "last_period_start": "2999-01-01",
                                                  "typical_cycle_length": "5", "typical_period_length": ""})
        self.assertEqual(r.status_code, 400)
