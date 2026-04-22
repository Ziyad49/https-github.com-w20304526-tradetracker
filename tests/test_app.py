import importlib
import os
import pathlib
import sys
import tempfile
import unittest


PROJECT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


class TradeTrackerAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")

        os.environ["TRADETRACKER_DB_PATH"] = self.db_path
        os.environ["TRADETRACKER_SEED_DEMO"] = "0"
        os.environ["TRADETRACKER_SECRET_KEY"] = "test-secret-key"
        os.environ["TRADETRACKER_DEBUG"] = "0"

        for module_name in ("database", "app"):
            if module_name in sys.modules:
                del sys.modules[module_name]

        self.database = importlib.import_module("database")
        self.app_module = importlib.import_module("app")
        self.app_module.app.config.update(TESTING=True)
        self.client = self.app_module.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _csrf_token(self, path="/login"):
        self.client.get(path)
        with self.client.session_transaction() as session:
            token = session.get("_csrf_token")
            if not token:
                token = "test-csrf-token"
                session["_csrf_token"] = token
            return token

    def _register_and_login(self):
        csrf = self._csrf_token("/register")
        response = self.client.post(
            "/register",
            data={
                "csrf_token": csrf,
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Check your email", response.data)

        user = self.database.get_user_by_email("test@example.com")
        self.assertIsNotNone(user)
        token = user[6]

        verify_page = self.client.get(f"/verify-email/{token}")
        self.assertEqual(verify_page.status_code, 200)
        self.assertIn(b"Create your password", verify_page.data)

        csrf = self._csrf_token(f"/verify-email/{token}")
        password_response = self.client.post(
            f"/set-password/{token}",
            data={
                "csrf_token": csrf,
                "password": "password123",
                "confirm_password": "password123",
            },
            follow_redirects=False,
        )
        self.assertEqual(password_response.status_code, 200)
        self.assertIn(b"Your account is ready", password_response.data)

        csrf = self._csrf_token("/login")
        response = self.client.post(
            "/login",
            data={
                "csrf_token": csrf,
                "email": "test@example.com",
                "password": "password123",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

    def test_calc_profit_handles_buy_and_sell(self):
        self.assertEqual(self.app_module.calc_profit("EURUSD", "BUY", 1.1000, 1.1050, 1), 50.0)
        self.assertEqual(self.app_module.calc_profit("EURUSD", "SELL", 1.1050, 1.1000, 1), 50.0)
        self.assertEqual(self.app_module.calc_profit("XAUUSD", "BUY", 2000.0, 2005.0, 1), 50.0)

    def test_register_login_and_logout_flow(self):
        self._register_and_login()

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)

        logout = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(logout.status_code, 302)
        self.assertIn("/", logout.headers["Location"])

    def test_post_routes_work_without_csrf_token(self):
        self._register_and_login()
        response = self.client.post(
            "/add_trade",
            data={
                "symbol": "EURUSD",
                "type": "BUY",
                "open": "1.1000",
                "close": "1.1050",
                "lot": "1",
                "risk": "Medium",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_login_requires_verified_account(self):
        csrf = self._csrf_token("/register")
        self.client.post(
            "/register",
            data={
                "csrf_token": csrf,
                "first_name": "Pending",
                "last_name": "User",
                "email": "pending@example.com",
            },
            follow_redirects=False,
        )

        csrf = self._csrf_token("/login")
        response = self.client.post(
            "/login",
            data={
                "csrf_token": csrf,
                "email": "pending@example.com",
                "password": "password123",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Please verify your email", response.data)

    def test_add_trade_creates_trade_for_logged_in_user(self):
        self._register_and_login()
        csrf = self._csrf_token("/trades")

        response = self.client.post(
            "/add_trade",
            data={
                "csrf_token": csrf,
                "symbol": "EURUSD",
                "type": "BUY",
                "open": "1.1000",
                "close": "1.1050",
                "lot": "1",
                "risk": "Medium",
                "strategy_id": "",
                "notes": "Breakout setup",
                "screenshot_url": "",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/trades", response.headers["Location"])

        summary = self.client.get("/api/summary")
        self.assertEqual(summary.status_code, 200)
        data = summary.get_json()
        self.assertEqual(data["trades"], 1)
        self.assertEqual(data["wins"], 1)
        self.assertEqual(data["net_profit"], 50.0)

    def test_add_strategy_and_journal_entry(self):
        self._register_and_login()

        csrf = self._csrf_token("/strategies")
        strategy_response = self.client.post(
            "/add_strategy",
            data={
                "csrf_token": csrf,
                "name": "Breakout",
                "description": "Break of structure with momentum confirmation",
            },
            follow_redirects=False,
        )
        self.assertEqual(strategy_response.status_code, 302)

        strategies = self.client.get("/api/strategies")
        self.assertEqual(strategies.status_code, 200)
        strategy_data = strategies.get_json()
        self.assertEqual(len(strategy_data), 1)
        self.assertEqual(strategy_data[0]["name"], "Breakout")

        csrf = self._csrf_token("/journal")
        journal_response = self.client.post(
            "/add_journal",
            data={
                "csrf_token": csrf,
                "entry_date": "2026-04-20",
                "mood": "Focused",
                "notes": "Followed the plan and respected risk.",
            },
            follow_redirects=False,
        )
        self.assertEqual(journal_response.status_code, 302)

        journal = self.client.get("/api/journal")
        self.assertEqual(journal.status_code, 200)
        entries = journal.get_json()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["mood"], "Focused")


if __name__ == "__main__":
    unittest.main()
