from io import StringIO
import re
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

    def test_bootstrap_generates_eight_character_password(self):
        output = StringIO()
        with patch.dict("os.environ", {"ENTRYSTAGE_ADMIN_PASSWORD": ""}):
            call_command("bootstrap_admin", username="initial-admin", no_input=True, stdout=output)
        password = re.search(r"Initial password: ([A-Za-z0-9]{8})\b", output.getvalue())
        self.assertIsNotNone(password)
        self.assertTrue(User.objects.get(username="initial-admin").check_password(password.group(1)))

    def test_reissue_member_activates_only_reclaimed_accounts(self):
        self.client.force_login(self.admin)
        browser = Client()
        browser.force_login(self.member)
        endpoint = f"/api/auth/members/{self.member.pk}/"
        self.assertEqual(browser.post(endpoint + "reissue/").status_code, 403)
        self.assertEqual(self.client.post(endpoint + "reissue/").status_code, 400)
        self.assertEqual(self.client.post(endpoint + "reclaim/").status_code, 200)
        self.assertIsNone(browser.get("/api/auth/session/").json()["user"])
        response = self.client.post(endpoint + "reissue/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        restored = response.json()["initial_password"]
        self.assertRegex(restored, r"^[A-Za-z0-9]{8}$")
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active and self.member.check_password(restored))
        self.assertEqual(self.client.post(f"/api/auth/members/{self.admin.pk}/reissue/").status_code, 404)

    def test_members_api_generates_password_when_omitted(self):
        self.client.force_login(self.admin)
        response = self.client.post("/api/auth/members/", {"username": "entrant"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Cache-Control"], "no-store")
        password = response.json()["initial_password"]
        self.assertRegex(password, r"^[A-Za-z0-9]{8}$")
        member = User.objects.get(username="entrant")
        self.assertTrue(member.check_password(password))
        self.assertNotIn("initial_password", self.client.get("/api/auth/members/").json()[0])

        reset = self.client.post(f"/api/auth/members/{member.pk}/reset-password/", {})
        self.assertEqual(reset.status_code, 200)
        updated = reset.json()["initial_password"]
        self.assertRegex(updated, r"^[A-Za-z0-9]{8}$")
        member.refresh_from_db()
        self.assertTrue(member.check_password(updated))

    def test_only_admins_can_reopen_current_issued_password(self):
        self.client.force_login(self.admin)
        result = self.client.post("/api/auth/members/", {"username": "new-member"}).json()
        endpoint = f'/api/auth/members/{result["id"]}/issued-password/'
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response.json(), {"initial_password": result["initial_password"]})
        self.assertEqual(Client().get(endpoint).status_code, 403)
        ordinary = Client()
        ordinary.force_login(self.member)
        self.assertEqual(ordinary.get(endpoint).status_code, 403)
        self.assertEqual(self.client.get(f"/api/auth/members/{self.admin.pk}/issued-password/").status_code, 404)
        self.assertTrue(all("initial_password" not in entry for entry in self.client.get("/api/auth/members/").json()))

    def test_reset_and_reissue_make_a_new_password_available(self):
        self.client.force_login(self.admin)
        browser = Client()
        browser.force_login(self.member)
        endpoint = f"/api/auth/members/{self.member.pk}/"
        self.assertIsNone(self.client.get(endpoint + "issued-password/").json()["initial_password"])
        reset = self.client.post(endpoint + "reset-password/", {}).json()
        self.assertTrue(reset["is_active"])
        self.assertRegex(reset["initial_password"], r"^[A-Za-z0-9]{8}$")
        self.assertEqual(self.client.get(endpoint + "issued-password/").json(), {"initial_password": reset["initial_password"]})
        self.assertIsNone(browser.get("/api/auth/session/").json()["user"])
        self.assertEqual(self.client.post(endpoint + "reclaim/").status_code, 200)
        self.assertIsNone(self.client.get(endpoint + "issued-password/").json()["initial_password"])
        issued = self.client.post(endpoint + "reissue/").json()
        self.assertEqual(self.client.get(endpoint + "issued-password/").json(), {"initial_password": issued["initial_password"]})

    def test_member_password_change_clears_previous_issued_password(self):
        self.client.force_login(self.admin)
        created = self.client.post("/api/auth/members/", {"username": "change-member"}).json()
        endpoint = f'/api/auth/members/{created["id"]}/issued-password/'
        user = User.objects.get(pk=created["id"])
        browser = Client()
        browser.force_login(user)
        password = "My-updated-member-password456!"
        response = browser.post("/api/auth/password/", {
            "current_password": created["initial_password"],
            "password": password,
        })
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(password))
        self.assertIsNone(self.client.get(endpoint).json()["initial_password"])
