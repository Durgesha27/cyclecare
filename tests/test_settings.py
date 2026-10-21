from tests.base import AppTestCase


class SettingsTests(AppTestCase):
    def setUp(self):
        super().setUp(); self.c = self.new_user()

    def test_page_and_profile(self):
        self.assertEqual(self.c.get("/settings").status_code, 200)
        r = self.c.post("/settings/profile", data={"csrf_token": self.token(self.c), "display_name": "Bea"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("Hello, Bea", self.c.get("/dashboard").get_data(as_text=True))
        self.assertEqual(self.c.post("/settings/profile", data={"csrf_token": self.token(self.c), "display_name": ""}).status_code, 400)

    def test_preferences_form_and_api(self):
        r = self.c.post("/settings/preferences", data={"csrf_token": self.token(self.c), "typical_cycle_length": "31",
                                                       "typical_period_length": "4", "reminders_enabled": "1"})
        self.assertEqual(r.status_code, 302)
        p = self.c.get("/api/preferences").get_json()["preferences"]
        self.assertEqual((p["typical_cycle_length"], p["typical_period_length"], p["reminders_enabled"]), (31, 4, True))
        bad = self.c.post("/settings/preferences", data={"csrf_token": self.token(self.c), "typical_cycle_length": "3"})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.api(self.c, "put", "/api/preferences", {"typical_cycle_length": 500}).status_code, 422)
        self.assertEqual(self.api(self.c, "put", "/api/preferences", {"reminders_enabled": "maybe"}).status_code, 422)
        ok = self.api(self.c, "put", "/api/preferences", {"typical_cycle_length": None})
        self.assertIsNone(ok.get_json()["preferences"]["typical_cycle_length"])

    def test_reminder_banner_only_when_enabled_and_close(self):
        self.api(self.c, "post", "/api/periods", {"start_date": self.day(56), "end_date": self.day(52)})
        self.api(self.c, "post", "/api/periods", {"start_date": self.day(27), "end_date": self.day(23)})  # next est: tomorrow
        self.assertNotIn("Reminder:", self.c.get("/dashboard").get_data(as_text=True))
        self.api(self.c, "put", "/api/preferences", {"reminders_enabled": True})
        self.assertIn("Reminder:", self.c.get("/dashboard").get_data(as_text=True))

    def test_export_download(self):
        self.api(self.c, "post", "/api/periods", {"start_date": self.day(10), "end_date": self.day(7)})
        self.api(self.c, "post", "/api/symptoms", {"date": self.day(1), "mood": "Calm"})
        r = self.c.get("/settings/export")
        self.assertIn("attachment", r.headers["Content-Disposition"])
        d = r.get_json()
        self.assertEqual(len(d["periods"]), 1); self.assertEqual(len(d["symptoms"]), 1)
        self.assertNotIn("password", r.get_data(as_text=True).lower())

    def test_every_page_renders(self):
        for url in ("/dashboard", "/calendar", "/log-period", "/history", "/symptoms", "/insights", "/settings"):
            self.assertEqual(self.c.get(url).status_code, 200, url)

    def test_db_not_wiped_on_restart(self):
        from app import create_app
        create_app({"TESTING": True, "DATABASE": self.path, "SECRET_KEY": "x"})
        self.assertEqual(self.c.get("/dashboard").status_code, 200)
