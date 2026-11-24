from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

User = get_user_model()


class AccountTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="reviewer", password="initial-admin-pass123!")
        self.member = User.objects.create_user(username="team-member", password="first-member-pass123!")

    def test_login_requires_csrf_and_no_public_registration(self):
        browser = Client(enforce_csrf_checks=True)
        credentials = {"username": self.member.username, "password": "first-member-pass123!"}
        self.assertEqual(browser.post("/api/auth/login/", credentials).status_code, 403)
        token = browser.get("/api/auth/session/").json()["csrf_token"]
        response = browser.post("/api/auth/login/", credentials, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["user"]["username"], self.member.username)
        self.assertEqual(browser.post("/api/auth/register/", credentials).status_code, 404)
        self.assertEqual(browser.post("/api/auth/logout/", {}, HTTP_X_CSRFTOKEN=response.json()["csrf_token"]).status_code, 200)
        self.assertIsNone(browser.get("/api/auth/session/").json()["user"])

    def test_administrator_creates_and_reclaims_accounts(self):
        browser = Client()
        browser.force_login(self.member)
        self.assertEqual(browser.get("/api/auth/members/").status_code, 403)
        self.client.force_login(self.admin)
        created = self.client.post("/api/auth/members/", {"username": "entrant", "password": "entrant-password-789!"})
        self.assertEqual(created.status_code, 201, created.content)
        self.assertFalse(created.json()["is_admin"])
        self.assertNotIn("password", created.json())

        endpoint = f"/api/auth/members/{self.member.pk}/"
        self.assertEqual(self.client.post(endpoint + "reclaim/").status_code, 200)
        self.assertIsNone(browser.get("/api/auth/session/").json()["user"])
        self.assertEqual(browser.post("/api/auth/login/", {"username": self.member.username, "password": "first-member-pass123!"}).status_code, 401)
        restored = self.client.post(endpoint + "reset-password/", {"password": "renewed-member-pass123!", "reactivate": True})
        self.assertTrue(restored.json()["is_active"])
        self.assertIsNone(browser.get("/api/auth/session/").json()["user"])
        self.assertEqual(browser.post("/api/auth/login/", {"username": self.member.username, "password": "renewed-member-pass123!"}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/auth/members/{self.admin.pk}/reclaim/").status_code, 404)

    def test_initial_administrator_is_idempotent(self):
        with patch.dict("os.environ", {"ENTRYSTAGE_ADMIN_PASSWORD": "bootstrap-Admin-19$"}):
            call_command("bootstrap_admin", username="initial-admin", no_input=True, stdout=StringIO())
            call_command("bootstrap_admin", username="initial-admin", no_input=True, stdout=StringIO())
        entry = User.objects.get(username="initial-admin")
        self.assertTrue(entry.is_staff and entry.is_superuser and entry.check_password("bootstrap-Admin-19$"))
