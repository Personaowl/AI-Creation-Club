from io import BytesIO
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import ZipFile

import jwt
import pypdfium2 as pdfium
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from .models import AccessChange, Asset, Work

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


def sample_pdf():
    content = BytesIO()
    with pdfium.PdfDocument.new() as document:
        document.new_page(600, 400)
        document.new_page(400, 600)
        document.save(content)
    return content.getvalue()


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

    def test_optional_work_details_survive_edit_and_publish(self):
        work = self.draft()
        address = f"/api/works/{work}/"
        old_payload = self.author.get(address).json()
        details = {"competition_name": "创意竞赛", "team_name": "星光团队", "team_members": "成员一\n成员二"}
        for name in details:
            self.assertEqual(old_payload[name], "")
        result = self.author.patch(address, details, content_type="application/json")
        self.assertEqual(result.status_code, 200, result.content)
        self.attachment(work, pptx())
        self.publish(work)
        published = self.viewer.get(address).json()
        self.assertEqual({name: published[name] for name in details}, details)
        self.assertContains(self.client.get(f"/admin/works/work/{work}/change/"), details["team_name"])

    def test_only_author_can_withdraw_pending_work_and_resubmit(self):
        work = self.draft()
        asset = self.attachment(work, pptx())
        url = f"/api/works/{work}/"
        submit = url + "submit/"
        withdraw = url + "withdraw/"
        review = f"/api/manage/works/{work}/review/"
        self.assertEqual(self.author.post(withdraw).status_code, 400)
        self.assertEqual(self.author.post(submit).status_code, 200)
        self.assertEqual(self.viewer.post(withdraw).status_code, 404)
        self.assertEqual(self.client.post(withdraw).status_code, 403)
        self.assertEqual([item["id"] for item in self.client.get("/api/works/?scope=review").json()], [work])

        response = self.author.post(withdraw)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], Work.Status.DRAFT)
        self.assertTrue(response.json()["can_edit"])
        self.assertEqual([item["id"] for item in response.json()["assets"]], [asset])
        self.assertEqual(response.json()["description"], "项目介绍")
        self.assertEqual(self.client.get("/api/works/?scope=review").json(), [])
        self.assertEqual(self.client.post(review, {"decision": "approved"}).status_code, 400)

        self.assertEqual(self.author.patch(url, {"title": "撤回后修改"}, content_type="application/json").status_code, 200)
        self.assertEqual(self.author.post(submit).json()["status"], Work.Status.PENDING)
        self.assertEqual(self.client.post(review, {"decision": "approved"}).status_code, 200)
        self.assertEqual(self.author.post(withdraw).status_code, 400)
        self.assertEqual(Work.objects.get(pk=work).status, Work.Status.APPROVED)

    def test_pdf_and_mp3_preview_respect_work_permissions(self):
        work = self.draft()
        pdf_content = sample_pdf()
        mp3_content = b"ID3\x04\x00\x00\x00\x00\x00\x04tag!" + (b"\xff\xfb\x90\x64" + bytes(413)) * 8
        pdf = self.attachment(work, SimpleUploadedFile("创意方案.PDF", pdf_content))
        audio = self.attachment(work, SimpleUploadedFile("配乐.mp3", mp3_content))
        self.assertEqual(Asset.objects.get(pk=pdf).kind, Asset.Kind.PDF)
        self.assertEqual(Asset.objects.get(pk=audio).kind, Asset.Kind.AUDIO)
        pdf_url = f"/api/works/{work}/assets/{pdf}/"
        audio_url = f"/api/works/{work}/assets/{audio}/"
        self.assertEqual(self.viewer.get(pdf_url + "pdf/1/").status_code, 404)
        self.assertEqual(self.viewer.get(audio_url + "audio/").status_code, 404)
        self.publish(work)
        page = self.viewer.get(pdf_url + "pdf/2/")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page["Content-Type"], "image/png")
        self.assertEqual(page["X-Page-Count"], "2")
        self.assertEqual(page["Cache-Control"], "private, no-store")
        self.assertTrue(page.content.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(self.viewer.get(pdf_url + "pdf/3/").status_code, 404)
        self.assertEqual(self.viewer.get(pdf_url + "audio/").status_code, 404)
        stream = self.viewer.get(audio_url + "audio/", HTTP_RANGE="bytes=14-17")
        self.assertEqual(stream.status_code, 206)
        self.assertEqual(stream["Content-Type"], "audio/mpeg")
        self.assertEqual(b"".join(stream.streaming_content), b"\xff\xfb\x90\x64")
        for base, original in ((pdf_url, pdf_content), (audio_url, mp3_content)):
            self.assertEqual(self.viewer.get(base + "download/").status_code, 403)
            self.assertEqual(b"".join(self.client.get(base + "download/").streaming_content), original)
        access = f"/api/manage/works/{work}/access/"
        self.client.patch(access, {"allow_download": True}, content_type="application/json")
        for base, original in ((pdf_url, pdf_content), (audio_url, mp3_content)):
            response = self.viewer.get(base + "download/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment", response["Content-Disposition"])
            self.assertEqual(b"".join(response.streaming_content), original)
        self.client.patch(access, {"is_visible": False}, content_type="application/json")
        self.assertEqual(self.viewer.get(pdf_url + "pdf/1/").status_code, 404)
        self.assertEqual(self.viewer.get(audio_url + "audio/").status_code, 404)

    def test_malformed_pdf_and_mp3_are_rejected(self):
        work = self.draft()
        address = f"/api/works/{work}/assets/"
        for name, content in (("bad.pdf", b"%PDF-1.7\ninvalid"), ("bad.mp3", b"ID3\x04\x00\x00\x00\x00\x00\x00broken")):
            with self.subTest(name=name):
                response = self.author.post(address, {"file": SimpleUploadedFile(name, content)})
                self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Asset.objects.filter(work_id=work).exists())

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
