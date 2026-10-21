from tests.base import AppTestCase


class AccessControlTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.a = self.new_user("a@example.com", "A"); self.b = self.new_user("b@example.com", "B")
        self.pid = self.api(self.a, "post", "/api/periods", {"start_date": self.day(10), "end_date": self.day(7), "notes": "private"}).get_json()["period"]["id"]
        self.sid = self.api(self.a, "post", "/api/symptoms", {"date": self.day(1), "mood": "Calm"}).get_json()["entry"]["id"]

    def test_other_user_cannot_touch_period(self):
        self.assertEqual(self.b.get(f"/api/periods/{self.pid}").status_code, 404)
        self.assertEqual(self.api(self.b, "put", f"/api/periods/{self.pid}", {"start_date": self.day(9)}).status_code, 404)
        self.assertEqual(self.api(self.b, "delete", f"/api/periods/{self.pid}").status_code, 404)
        self.assertEqual(self.b.get(f"/log-period?id={self.pid}").status_code, 404)
        self.assertEqual(self.b.get("/api/periods").get_json()["periods"], [])
        self.assertNotIn("private", self.b.get("/history").get_data(as_text=True))
        self.assertEqual(self.a.get(f"/api/periods/{self.pid}").status_code, 200)  # still intact

    def test_other_user_cannot_touch_symptoms(self):
        self.assertEqual(self.b.get(f"/api/symptoms/{self.sid}").status_code, 404)
        self.assertEqual(self.api(self.b, "put", f"/api/symptoms/{self.sid}", {"date": self.day(1), "mood": "Low"}).status_code, 404)
        self.assertEqual(self.api(self.b, "delete", f"/api/symptoms/{self.sid}").status_code, 404)
        self.assertEqual(self.b.get("/api/symptoms").get_json()["entries"], [])

    def test_same_dates_allowed_for_different_users(self):
        r = self.api(self.b, "post", "/api/periods", {"start_date": self.day(10), "end_date": self.day(7)})
        self.assertEqual(r.status_code, 201)

    def test_user_scoped_calendar_insights_export(self):
        self.assertEqual(self.b.get("/api/calendar").get_json()["periods"], [])
        self.assertEqual(self.b.get("/api/insights").get_json()["recorded_periods"], 0)
        self.assertEqual(self.b.get("/settings/export").get_json()["periods"], [])

    def test_unauthenticated_api_gets_401(self):
        anon = self.app.test_client()
        for url in ("/api/periods", "/api/symptoms", "/api/preferences", "/api/insights", "/api/calendar"):
            self.assertEqual(anon.get(url).status_code, 401, url)
        self.assertEqual(anon.get(f"/api/periods/{self.pid}").status_code, 401)

    def test_api_writes_require_csrf(self):
        for method, url, body in (("post", "/api/periods", {"start_date": self.day(3)}),
                                  ("put", f"/api/periods/{self.pid}", {"start_date": self.day(10)}),
                                  ("delete", f"/api/periods/{self.pid}", None),
                                  ("post", "/api/symptoms", {"date": self.day(2), "mood": "Calm"}),
                                  ("put", "/api/preferences", {"typical_cycle_length": 30})):
            r = getattr(self.a, method)(url, json=body)
            self.assertEqual(r.status_code, 403, url)
        r = self.a.delete(f"/api/periods/{self.pid}", headers={"X-CSRF-Token": "wrong"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.a.get(f"/api/periods/{self.pid}").status_code, 200)

    def test_account_deletion_removes_everything_and_only_own(self):
        self.api(self.a, "put", "/api/preferences", {"typical_cycle_length": 30})
        bad = self.a.post("/settings/delete", data={"csrf_token": self.token(self.a), "password": "wrong", "confirm_text": "DELETE"})
        self.assertEqual(bad.status_code, 400)
        bad2 = self.a.post("/settings/delete", data={"csrf_token": self.token(self.a), "password": "Sup3rSecret", "confirm_text": "nope"})
        self.assertEqual(bad2.status_code, 400)
        ok = self.a.post("/settings/delete", data={"csrf_token": self.token(self.a), "password": "Sup3rSecret", "confirm_text": "DELETE"})
        self.assertEqual(ok.status_code, 302)
        import sqlite3
        db = sqlite3.connect(self.path)
        for t in ("period_records", "symptom_entries", "cycle_preferences"):
            self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id=1").fetchone()[0], 0, t)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        self.assertEqual(self.a.get("/dashboard").status_code, 302)
        self.assertEqual(self.b.get("/dashboard").status_code, 200)
