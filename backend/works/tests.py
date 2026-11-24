from io import BytesIO
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import ZipFile

import jwt
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import AccessChange, Work

User = get_user_model()
DOCS_ORIGIN = "http://docs.example.test"
SOURCE_ORIGIN = "http://api.internal"
BROWSER_SECRET = "test-browser-secret-only-" * 2
OUTBOX_SECRET = "test-outbox-secret-only-" * 2


def pptx():
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/presentation.xml", "<presentation/>")
    return SimpleUploadedFile("现场答辩.pptx", content.getvalue())


class WorkTests(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=directory))
        self.owner = User.objects.create_user(username="entrant")
        self.other = User.objects.create_user(username="viewer")
        self.admin = User.objects.create_superuser(username="reviewer")
        self.author = Client()
        self.author.force_login(self.owner)
        self.viewer = Client()
        self.viewer.force_login(self.other)
        self.client.force_login(self.admin)

    def draft(self, title="竞赛作品"):
        response = self.author.post("/api/works/", {"title": title, "description": "项目介绍"})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["id"]

    def attachment(self, work, uploaded):
        response = self.author.post(f"/api/works/{work}/assets/", {"file": uploaded})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn("file", response.json())
        return response.json()["id"]

    def publish(self, work, download=False):
        self.assertEqual(self.author.post(f"/api/works/{work}/submit/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/manage/works/{work}/review/", {"decision": "approved"}).status_code, 200)
        self.assertEqual(self.viewer.get(f"/api/works/{work}/").status_code, 404)
        response = self.client.patch(f"/api/manage/works/{work}/access/", {"is_visible": True, "allow_download": download}, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)

    def test_work_review_display_and_download_are_work_scoped(self):
        self.assertEqual(Client().get("/api/works/").status_code, 403)
        work = self.draft()
        file_one = self.attachment(work, pptx())
        file_two = self.attachment(work, SimpleUploadedFile("演示.mp4", b"\x00\x00\x00\x14ftypisom0123456789"))
        self.assertEqual(self.viewer.get("/api/works/").json(), [])
        self.assertEqual(self.viewer.get(f"/api/works/{work}/").status_code, 404)
        self.assertEqual(self.viewer.get(f"/api/works/{work}/assets/{file_one}/download/").status_code, 404)
        self.assertEqual(self.viewer.post(f"/api/manage/works/{work}/review/", {"decision": "approved"}).status_code, 403)
        self.publish(work)
        self.assertEqual(len(self.viewer.get("/api/works/").json()[0]["assets"]), 2)
        for asset in (file_one, file_two):
            self.assertEqual(self.viewer.get(f"/api/works/{work}/assets/{asset}/download/").status_code, 403)
        response = self.viewer.get(f"/api/works/{work}/assets/{file_two}/video/", HTTP_RANGE="bytes=4-7")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(b"".join(response.streaming_content), b"ftyp")
        self.assertEqual(self.client.patch(f"/api/manage/works/{work}/access/", {"allow_download": True}, content_type="application/json").status_code, 200)
        response = self.viewer.get(f"/api/works/{work}/assets/{file_one}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"PK"))
        self.client.patch(f"/api/manage/works/{work}/access/", {"is_visible": False}, content_type="application/json")
        self.assertEqual(self.viewer.get(f"/api/works/{work}/assets/{file_one}/download/").status_code, 404)
        self.assertEqual(self.viewer.get(f"/api/works/{work}/assets/{file_two}/video/").status_code, 404)
        self.assertEqual(self.viewer.get("/api/works/").json(), [])
        self.assertEqual(self.author.get(f"/api/works/{work}/").status_code, 200)
        self.assertEqual(
            list(AccessChange.objects.filter(work_id=work).values_list("is_visible", "allow_download")),
            [(False, True), (True, True), (True, False)],
        )

    def test_rejection_requires_a_reason_and_accepts_resubmission(self):
        work = self.draft()
        address = f"/api/works/{work}/"
        submit = address + "submit/"
        review = f"/api/manage/works/{work}/review/"
        self.assertEqual(self.author.post(submit).status_code, 400)
        self.assertEqual(self.author.post(address + "assets/", {"file": SimpleUploadedFile("fake.pptx", b"bad")}).status_code, 400)
        self.attachment(work, pptx())
        self.assertEqual(self.author.post(submit).status_code, 200)
        self.assertEqual(self.author.patch(address, {"title": "不能改变"}, content_type="application/json").status_code, 403)
        self.assertEqual(self.client.post(review, {"decision": "rejected"}).status_code, 400)
        response = self.client.post(review, {"decision": "rejected", "note": "请补充说明。"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.author.get(address).json()["review_note"], "请补充说明。")
        self.assertEqual(self.author.patch(address, {"title": "已修改的作品"}, content_type="application/json").status_code, 200)
        self.assertEqual(self.author.post(submit).status_code, 200)

    @override_settings(
        ONLYOFFICE_URL=DOCS_ORIGIN, ONLYOFFICE_SOURCE_ORIGIN=SOURCE_ORIGIN,
        ONLYOFFICE_BROWSER_SECRET=BROWSER_SECRET, ONLYOFFICE_OUTBOX_SECRET=OUTBOX_SECRET,
    )
    def test_ppt_source_requires_signed_office_request_and_current_permission(self):
        work = self.draft()
        file_id = self.attachment(work, pptx())
        self.publish(work)
        address = f"/api/works/{work}/assets/{file_id}/"
        config = self.viewer.get(address + "presentation/").json()["config"]
        self.assertEqual(config["document"]["fileType"], "pptx")
        self.assertFalse(config["document"]["permissions"]["download"])
        self.assertEqual(config["editorConfig"]["mode"], "view")
        self.assertEqual(self.viewer.get(address + "viewer/").status_code, 200)
        self.assertEqual(self.viewer.get(address + "download/").status_code, 403)
        document_url = config["document"]["url"]
        private_path = urlsplit(document_url)
        relative = f"{private_path.path}?{private_path.query}"
        self.assertEqual(self.viewer.get(relative).status_code, 404)
        headers = {"HTTP_AUTHORIZATION": "Bearer " + jwt.encode({"payload": {"url": document_url}}, OUTBOX_SECRET, algorithm="HS256")}
        response = Client().get(relative, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content).startswith(b"PK"))
        self.client.patch(f"/api/manage/works/{work}/access/", {"is_visible": False}, content_type="application/json")
        self.assertEqual(Client().get(relative, **headers).status_code, 404)
        self.assertEqual(self.viewer.get(address + "viewer/").status_code, 404)

    def test_admin_can_open_moderation_and_member_pages(self):
        work = self.draft()
        self.attachment(work, pptx())
        self.assertEqual(self.author.post(f"/api/works/{work}/submit/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/works/work/{work}/change/").status_code, 200)
        self.assertEqual(self.client.get("/admin/auth/user/add/").status_code, 200)
        self.assertEqual(Work.objects.get(pk=work).status, Work.Status.PENDING)
