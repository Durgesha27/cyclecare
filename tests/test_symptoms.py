from tests.base import AppTestCase


class SymptomTests(AppTestCase):
    def setUp(self):
        super().setUp(); self.c = self.new_user()

    def make(self, **kw):
        body = {"date": self.day(1), "mood": "Calm", "symptoms": ["Cramps", "Fatigue"], "severity": 2, "notes": "ok"}
        body.update(kw)
        return self.api(self.c, "post", "/api/symptoms", body)

    def test_create_get_list(self):
        r = self.make(); self.assertEqual(r.status_code, 201)
        e = r.get_json()["entry"]; self.assertEqual(e["symptoms"], ["Cramps", "Fatigue"])
        self.assertEqual(self.c.get(f"/api/symptoms/{e['id']}").get_json()["entry"]["mood"], "Calm")
        self.assertEqual(len(self.c.get("/api/symptoms").get_json()["entries"]), 1)

    def test_all_fields_optional_but_something_required(self):
        self.assertEqual(self.make(mood=None, symptoms=[], severity=None, notes=None).status_code, 422)
        self.assertEqual(self.make(mood=None, symptoms=[], severity=None, notes="just a note").status_code, 201)

    def test_validation(self):
        self.assertEqual(self.make(mood="Ecstatic").status_code, 422)
        self.assertEqual(self.make(symptoms=["Plague"]).status_code, 422)
        self.assertEqual(self.make(symptoms="Cramps").status_code, 422)
        self.assertEqual(self.make(severity=9).status_code, 422)
        self.assertEqual(self.make(severity="strong").status_code, 422)
        self.assertEqual(self.make(date="2999-01-01").status_code, 422)
        self.assertEqual(self.make(date="x").status_code, 422)
        self.assertEqual(self.make(notes="n" * 501).status_code, 422)

    def test_duplicate_date(self):
        self.make(); self.assertEqual(self.make().status_code, 409)

    def test_edit_delete(self):
        sid = self.make().get_json()["entry"]["id"]
        r = self.api(self.c, "put", f"/api/symptoms/{sid}", {"date": self.day(1), "mood": "Low", "symptoms": ["Headache"], "severity": 1})
        self.assertEqual(r.get_json()["entry"]["mood"], "Low")
        self.assertEqual(self.api(self.c, "put", f"/api/symptoms/{sid}", {"date": self.day(1), "mood": "Nope"}).status_code, 422)
        self.assertEqual(self.api(self.c, "delete", f"/api/symptoms/{sid}").status_code, 200)
        self.assertEqual(self.c.get(f"/api/symptoms/{sid}").status_code, 404)

    def test_date_filter_and_page(self):
        self.make(date=self.day(10)); self.make(date=self.day(2))
        r = self.c.get(f"/api/symptoms?from={self.day(5)}").get_json()["entries"]
        self.assertEqual([e["date"] for e in r], [self.day(2)])
        self.assertEqual(self.c.get("/api/symptoms?from=bad").status_code, 400)
        html = self.c.get(f"/symptoms?to={self.day(5)}").get_data(as_text=True)
        self.assertIn(self.day(10), html); self.assertNotIn(self.day(2), html.split("Previous check-ins")[1])
        self.assertEqual(self.c.get("/symptoms").status_code, 200)

    def test_html_in_notes_is_escaped(self):
        self.make(notes="<script>alert(1)</script>")
        html = self.c.get("/symptoms").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
