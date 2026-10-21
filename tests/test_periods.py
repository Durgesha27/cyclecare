from tests.base import AppTestCase


class PeriodTests(AppTestCase):
    def setUp(self):
        super().setUp(); self.c = self.new_user()

    def create(self, start, end=None, notes=None):
        return self.api(self.c, "post", "/api/periods", {"start_date": start, "end_date": end, "notes": notes})

    def test_create_and_list(self):
        r = self.create(self.day(20), self.day(16), "note")
        self.assertEqual(r.status_code, 201)
        p = r.get_json()["period"]; self.assertEqual(p["duration_days"], 5); self.assertFalse(p["ongoing"])
        self.assertEqual(len(self.c.get("/api/periods").get_json()["periods"]), 1)
        self.assertEqual(self.c.get(f"/api/periods/{p['id']}").status_code, 200)

    def test_ongoing_period_without_end(self):
        p = self.create(self.day(2)).get_json()["period"]
        self.assertTrue(p["ongoing"]); self.assertIsNone(p["end_date"]); self.assertIsNone(p["duration_days"])

    def test_validation_errors(self):
        self.assertEqual(self.create(self.day(5), self.day(8)).status_code, 422)      # end before start
        self.assertEqual(self.create("2999-01-01").status_code, 422)                   # future
        self.assertEqual(self.create("not-a-date").status_code, 422)
        self.assertEqual(self.create(None).status_code, 422)
        self.assertEqual(self.create(self.day(40), self.day(10)).status_code, 422)     # too long
        self.assertEqual(self.create(self.day(5), notes="x" * 501).status_code, 422)
        self.assertEqual(self.api(self.c, "post", "/api/periods", None).status_code, 422)
        self.assertEqual(self.api(self.c, "post", "/api/periods", {"start_date": 123}).status_code, 422)

    def test_duplicate_and_overlap_rejected(self):
        self.create(self.day(30), self.day(26))
        self.assertEqual(self.create(self.day(30)).status_code, 409)
        self.assertEqual(self.create(self.day(28), self.day(27)).status_code, 409)
        self.assertEqual(self.create(self.day(20), self.day(16)).status_code, 201)  # separate: fine

    def test_open_period_blocks_overlap_but_not_later_cycle(self):
        self.create(self.day(60))                      # ongoing, forgotten end
        self.assertEqual(self.create(self.day(55), self.day(52)).status_code, 409)
        self.assertEqual(self.create(self.day(30), self.day(26)).status_code, 201)

    def test_gap_between_records_not_filled(self):
        self.create(self.day(40), self.day(36)); self.create(self.day(12), self.day(8))
        d = self.c.get("/api/calendar").get_json()
        days = {x for p in d["periods"] for x in p["days"]}
        self.assertNotIn(self.day(25), days)

    def test_edit_and_delete(self):
        pid = self.create(self.day(10), self.day(7)).get_json()["period"]["id"]
        r = self.api(self.c, "put", f"/api/periods/{pid}", {"start_date": self.day(10), "end_date": self.day(6), "notes": "fixed"})
        self.assertEqual(r.status_code, 200); self.assertEqual(r.get_json()["period"]["notes"], "fixed")
        self.assertEqual(self.api(self.c, "put", f"/api/periods/{pid}", {"start_date": self.day(10), "end_date": self.day(12)}).status_code, 422)
        self.assertEqual(self.api(self.c, "delete", f"/api/periods/{pid}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/periods/{pid}").status_code, 404)

    def test_edit_can_keep_own_dates(self):
        pid = self.create(self.day(10), self.day(7)).get_json()["period"]["id"]
        self.assertEqual(self.api(self.c, "put", f"/api/periods/{pid}", {"start_date": self.day(10), "end_date": self.day(7)}).status_code, 200)

    def test_pages_render(self):
        pid = self.create(self.day(40), self.day(36)).get_json()["period"]["id"]
        self.create(self.day(12))
        h = self.c.get("/history").get_data(as_text=True)
        self.assertIn("28 days", h); self.assertIn("Ongoing", h)
        self.assertEqual(self.c.get("/history?order=asc").status_code, 200)
        self.assertEqual(self.c.get(f"/log-period?id={pid}").status_code, 200)
        self.assertEqual(self.c.get("/log-period?id=99999").status_code, 404)
        self.assertEqual(self.c.get("/log-period?id=abc").status_code, 404)

    def test_dashboard_empty_and_filled(self):
        self.assertIn("Start by recording a period", self.c.get("/dashboard").get_data(as_text=True))
        self.create(self.day(50), self.day(46)); self.create(self.day(22), self.day(18))
        html = self.c.get("/dashboard").get_data(as_text=True)
        self.assertIn("Next period (estimate)", html)
        self.assertIn("6 days until next period", html)          # 28-day interval, started 22 days ago
        self.assertIn('class="ring-marker-text"', html); self.assertIn(">23</text>", html)  # cycle day 23
        self.assertIn('class="ring"', html)
        self.assertEqual(html.count('class="week-day'), 7)
        self.assertNotIn("pregnan", html.lower()); self.assertNotIn("fertil", html.lower())

    def test_dashboard_ring_hidden_without_estimate(self):
        html = self.c.get("/dashboard").get_data(as_text=True)
        self.assertNotIn('class="ring"', html)
        self.create(self.day(5))  # one period only: no interval, no estimate
        html = self.c.get("/dashboard").get_data(as_text=True)
        self.assertNotIn('class="ring"', html); self.assertIn("Record one more period start", html)

    def test_dashboard_quick_overview_shows_todays_checkin(self):
        self.api(self.c, "post", "/api/symptoms", {"date": self.day(0), "mood": "Calm", "symptoms": ["Cramps"]})
        html = self.c.get("/dashboard").get_data(as_text=True)
        self.assertIn("Calm", html); self.assertIn("Cramps", html); self.assertIn("Edit check-in", html)

    def test_calendar_api(self):
        self.create(self.day(2))
        d = self.c.get("/api/calendar").get_json()
        self.assertEqual(len(d["periods"]), 1)
        self.assertEqual(self.c.get("/api/calendar?year=2024&month=2").status_code, 200)
        self.assertEqual(self.c.get("/api/calendar?year=2024&month=13").status_code, 400)
        self.assertEqual(self.c.get("/api/calendar?year=abc").status_code, 400)

    def test_insights_api(self):
        self.assertIsNotNone(self.c.get("/api/insights").get_json()["needs"])
        self.create(self.day(84), self.day(80)); self.create(self.day(56), self.day(52)); self.create(self.day(28), self.day(24))
        d = self.c.get("/api/insights").get_json()
        self.assertEqual(d["typical_cycle_length"], 28); self.assertEqual(len(d["durations"]), 3)
        self.assertEqual(self.c.get("/insights").status_code, 200)
