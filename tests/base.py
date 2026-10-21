import os, re, tempfile, unittest
from datetime import date, timedelta
from app import create_app

PW = "Sup3rSecret"


class AppTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.path, "SECRET_KEY": "test-key"})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.path)

    # helpers ---------------------------------------------------------
    def token(self, client=None):
        """Return the session's CSRF token, issuing one the way the app does (via a page render)."""
        client = client or self.client
        with client.session_transaction() as s:
            tok = s.get("_csrf")
        if tok:
            return tok
        client.get("/")  # any page render issues a token into the session
        with client.session_transaction() as s:
            return s["_csrf"]

    def signup(self, client=None, name="Ana", email="ana@example.com", pw=PW, confirm=None):
        client = client or self.client
        return client.post("/signup", data={"csrf_token": self.token(client), "display_name": name,
                                            "email": email, "password": pw,
                                            "confirm_password": pw if confirm is None else confirm})

    def new_user(self, email="ana@example.com", name="Ana"):
        c = self.app.test_client()
        r = self.signup(c, name=name, email=email)
        assert r.status_code == 302, r.get_data(as_text=True)
        c.post("/onboarding/skip", data={"csrf_token": self.token(c)})
        return c

    def api(self, client, method, url, json=None):
        return getattr(client, method)(url, json=json, headers={"X-CSRF-Token": self.token(client)})

    @staticmethod
    def day(offset):
        return (date.today() - timedelta(days=offset)).isoformat()
