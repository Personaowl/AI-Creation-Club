from contextlib import closing
from io import BytesIO
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import ZipFile

import jwt
import pypdfium2 as pdfium
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from .models import AccessChange, Asset, Work, WorkComment

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


def team_photo():
    with BytesIO() as content, Image.new("RGB", (1800, 900), "steelblue") as image:
        exif = Image.Exif()
        exif[315] = "Private camera owner"
        image.save(content, format="JPEG", exif=exif)
        return SimpleUploadedFile("比赛合照.jpg", content.getvalue())


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

    def draft(self, title="竞赛作品", award_info="未获奖"):
        response = self.author.post("/api/works/", {"title": title, "description": "项目介绍", "award_info": award_info})
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

    def test_competitions_are_created_by_admin_and_can_classify_existing_works(self):
        self.assertEqual(self.author.post("/api/manage/competitions/", {"name": "校赛"}).status_code, 403)
        self.assertEqual(Client().get("/api/competitions/").status_code, 403)
        response = self.client.post("/api/manage/competitions/", {"name": " Innovation   Cup "})
        self.assertEqual(response.status_code, 201)
        competition = response.json()
        self.assertEqual(competition["name"], "Innovation Cup")
        self.assertEqual(self.client.post("/api/manage/competitions/", {"name": "INNOVATION CUP"}).status_code, 400)
        self.assertEqual(self.client.post("/api/manage/competitions/", {"name": "   "}).status_code, 400)
        self.assertEqual(self.author.get("/api/competitions/").json(), [competition])

        work = self.draft()
        link = f"/api/works/{work}/"
        payload = {"competition": competition["id"], "competition_name": "自定义文本"}
        response = self.author.patch(link, payload, content_type="application/json")
        self.assertEqual(response.json()["competition_name"], competition["name"])
        self.assertEqual(self.author.patch(link, {"competition": competition["id"] + 1}, content_type="application/json").status_code, 400)
        self.attachment(work, pptx())
        self.publish(work)
        self.assertEqual(self.viewer.get(link).json()["competition"], competition["id"])

        access_link = f"/api/manage/works/{work}/access/"
        response = self.author.patch(access_link, {"competition": None}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        response = self.client.patch(access_link, {"competition": None}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["competition"])
        self.assertEqual(response.json()["competition_name"], "")
        self.assertTrue(response.json()["is_visible"])
        self.assertEqual(AccessChange.objects.filter(work_id=work).count(), 1)

    def test_admin_can_rename_or_delete_competitions_without_removing_works(self):
        def category(name):
            return self.client.post("/api/manage/competitions/", {"name": name}).json()["id"]

        competition_id = category("省赛")
        other_id = category("Global Cup")
        path = f"/api/manage/competitions/{competition_id}/"
        self.assertEqual(self.author.patch(path, {"name": "新名称"}, content_type="application/json").status_code, 403)
        self.assertEqual(self.viewer.delete(path).status_code, 403)
        for invalid in ("  ", "GLOBAL  CUP"):
            self.assertEqual(self.client.patch(path, {"name": invalid}, content_type="application/json").status_code, 400)
        self.assertEqual(self.client.patch(path, {}, content_type="application/json").status_code, 400)

        published = self.draft()
        other = self.draft("另一分类的作品")
        for work_id, category_id in ((published, competition_id), (other, other_id)):
            response = self.author.patch(f"/api/works/{work_id}/", {"competition": category_id}, content_type="application/json")
            self.assertEqual(response.status_code, 200)
        attachment = self.attachment(published, pptx())
        self.publish(published)
        public_path = f"/api/works/{published}/"
        revision_id = self.author.post(public_path + "revision/").json()["id"]

        renamed = self.client.patch(path, {"name": " 省级 创新赛 "}, content_type="application/json")
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json(), {"id": competition_id, "name": "省级 创新赛"})
        self.assertEqual(self.viewer.get(public_path).json()["competition_name"], "省级 创新赛")
        self.assertEqual(Work.objects.get(pk=revision_id).competition_name, "省级 创新赛")

        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertEqual(self.viewer.get("/api/competitions/").json(), [{"id": other_id, "name": "Global Cup"}])
        work = self.viewer.get(public_path).json()
        self.assertIsNone(work["competition"])
        self.assertEqual(work["competition_name"], "")
        self.assertTrue(work["is_visible"])
        self.assertEqual(work["assets"][0]["id"], attachment)
        self.assertTrue(Work.objects.filter(pk=revision_id, competition=None, competition_name="").exists())
        self.assertTrue(Work.objects.filter(pk=other, competition_id=other_id).exists())

    def test_comments_follow_publication_and_require_author_or_admin_to_delete(self):
        work = self.draft()
        other_work = self.draft("另一件作品")
        link = f"/api/works/{work}/comments/"
        self.assertEqual(self.author.get(link).status_code, 404)
        self.assertEqual(self.author.post(link, {"body": "未上架"}).status_code, 404)
        self.attachment(work, pptx())
        self.attachment(other_work, pptx())
        self.publish(work)
        self.publish(other_work)
        self.assertEqual(Client().get(link).status_code, 403)
        self.assertEqual(Client().post(link, {"body": "匿名"}).status_code, 403)
        for invalid in ("   ", "字" * 501):
            self.assertEqual(self.viewer.post(link, {"body": invalid}).status_code, 400)

        response = self.viewer.post(link, {"body": "  一条评论  ", "author": "其他账号"})
        self.assertEqual(response.status_code, 201)
        comment = response.json()
        self.assertEqual(comment["body"], "一条评论")
        self.assertEqual(comment["author"], self.other.username)
        self.assertFalse(self.author.get(link).json()["items"][0]["can_delete"])
        self.assertTrue(self.client.get(link).json()["items"][0]["can_delete"])
        delete = link + f'{comment["id"]}/'
        self.assertEqual(self.author.delete(delete).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/works/{other_work}/comments/{comment["id"]}/').status_code, 404)

        access_link = f"/api/manage/works/{work}/access/"
        self.client.patch(access_link, {"is_visible": False}, content_type="application/json")
        self.assertEqual(self.viewer.get(link).status_code, 404)
        self.assertEqual(self.viewer.delete(delete).status_code, 404)
        self.assertEqual(self.viewer.post(link, {"body": "已下架"}).status_code, 404)
        self.client.patch(access_link, {"is_visible": True}, content_type="application/json")
        self.assertEqual(self.viewer.get(link).json()["items"][0]["id"], comment["id"])
        self.assertEqual(self.viewer.delete(delete).status_code, 204)

        second = self.author.post(link, {"body": "管理员可以删除"}).json()
        self.assertEqual(self.client.delete(link + f'{second["id"]}/').status_code, 204)

    def test_comment_pages_use_a_stable_cursor(self):
        work = Work.objects.create(owner=self.owner, title="分页", status=Work.Status.APPROVED, is_visible=True)
        WorkComment.objects.bulk_create([
            WorkComment(work=work, author=self.other, body=str(index)) for index in range(25)
        ])
        url = f"/api/works/{work.pk}/comments/"
        first = self.viewer.get(url).json()
        self.assertEqual([entry["body"] for entry in first["items"]], [str(index) for index in range(24, 4, -1)])
        self.viewer.post(url, {"body": "新的评论"})
        second = self.viewer.get(url, {"before": first["next_before"]}).json()
        self.assertEqual([entry["body"] for entry in second["items"]], ["4", "3", "2", "1", "0"])
        self.assertIsNone(second["next_before"])
        self.assertEqual(self.viewer.get(url, {"before": "invalid"}).status_code, 400)

    def test_published_revision_replaces_content_only_after_approval(self):
        original = self.draft("上架版本")
        source = f"/api/works/{original}/"
        original_details = {"team_intro": "原团队介绍", "award_info": "评审中", "ip_details": "专利申请中"}
        self.assertEqual(self.author.patch(source, original_details, content_type="application/json").status_code, 200)
        kept = self.attachment(original, pptx())
        kept_photo = self.attachment(original, team_photo())
        removed = self.attachment(original, SimpleUploadedFile("旧附件.pdf", sample_pdf()))
        removed_file = Asset.objects.get(pk=removed).file
        self.publish(original, download=True)
        self.viewer.post(source + "comments/", {"body": "原有评论"})
        self.assertEqual(self.viewer.post(source + "revision/").status_code, 403)
        self.assertEqual(self.author.patch(source, {"title": "绕过审核"}, content_type="application/json").status_code, 403)

        response = self.author.post(source + "revision/")
        self.assertEqual(response.status_code, 200, response.content)
        revision = response.json()
        revision_link = f'/api/works/{revision["id"]}/'
        self.assertEqual(revision["revision_of"], original)
        self.assertEqual(revision["title"], "上架版本")
        self.assertEqual({name: revision[name] for name in original_details}, original_details)
        self.assertEqual(sum(asset["kind"] == Asset.Kind.PHOTO for asset in revision["assets"]), 1)
        self.assertEqual(self.author.post(source + "revision/").json()["id"], revision["id"])
        self.assertEqual([entry["id"] for entry in self.author.get("/api/works/?scope=mine").json()], [original])
        self.assertIsNone(self.viewer.get(source).json()["revision"])
        self.assertEqual(self.viewer.get(revision_link).status_code, 404)

        cloned_pdf = next(asset["id"] for asset in revision["assets"] if asset["extension"] == "pdf")
        self.assertNotEqual(cloned_pdf, removed)
        self.assertEqual(Asset.objects.get(pk=cloned_pdf).file.name, removed_file.name)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.author.delete(revision_link + f"assets/{cloned_pdf}/").status_code, 204)
        self.assertTrue(removed_file.storage.exists(removed_file.name))

        new_asset = self.attachment(revision["id"], SimpleUploadedFile("新版附件.pdf", sample_pdf()))
        updated_details = {"title": "修改后版本", "team_intro": "新版团队介绍", "award_info": "一等奖", "ip_details": "专利已授权"}
        self.assertEqual(self.author.patch(revision_link, updated_details, content_type="application/json").status_code, 200)
        self.assertEqual(self.author.post(revision_link + "submit/").status_code, 200)
        self.assertEqual(self.author.get(source).json()["revision"]["status"], Work.Status.PENDING)
        self.assertEqual(self.client.get("/api/works/?scope=review").json()[0]["id"], revision["id"])
        self.assertEqual(self.author.post(revision_link + "withdraw/").json()["status"], Work.Status.DRAFT)
        self.assertEqual(self.author.post(revision_link + "submit/").status_code, 200)
        self.assertEqual(self.viewer.get(source).json()["title"], "上架版本")
        self.assertEqual(self.viewer.get(source).json()["award_info"], original_details["award_info"])
        with closing(self.viewer.get(source + f"assets/{removed}/download/")) as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.viewer.get(revision_link + f"assets/{new_asset}/download/").status_code, 404)

        review = f'/api/manage/works/{revision["id"]}/review/'
        response = self.client.post(review, {"decision": "rejected", "note": "请补充信息"})
        self.assertEqual(response.json()["status"], Work.Status.REJECTED)
        self.assertEqual(self.viewer.get(source).json()["title"], "上架版本")
        self.assertEqual(self.author.post(revision_link + "submit/").status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(review, {"decision": "approved"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], original)
        self.assertFalse(removed_file.storage.exists(removed_file.name))
        self.assertEqual(self.author.get(revision_link).status_code, 404)
        current = self.viewer.get(source).json()
        self.assertEqual({name: current[name] for name in updated_details}, updated_details)
        self.assertTrue(current["is_visible"])
        self.assertTrue(current["can_download"])
        self.assertEqual({asset["id"] for asset in current["assets"]}, {kept, kept_photo, new_asset})
        with closing(self.viewer.get(source + f"assets/{kept_photo}/photo/")) as response:
            self.assertEqual(response.status_code, 200)
        with closing(self.viewer.get(source + f"assets/{new_asset}/download/")) as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.viewer.get(source + "comments/").json()["items"][0]["body"], "原有评论")
        self.assertEqual(Work.objects.get(pk=original).reviews.filter(is_revision=True).count(), 2)
        self.assertNotEqual(self.author.post(source + "revision/").json()["id"], revision["id"])

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
        details = {
            "competition_name": "创意竞赛", "team_name": "星光团队", "team_members": "成员一\n成员二",
            "team_intro": "团队分工", "ip_details": "论文已发表\n软著登记中",
        }
        for name in details:
            self.assertEqual(old_payload[name], "")
        result = self.author.patch(address, details, content_type="application/json")
        self.assertEqual(result.status_code, 200, result.content)
        self.attachment(work, pptx())
        self.publish(work)
        published = self.viewer.get(address).json()
        self.assertEqual({name: published[name] for name in details}, details)
        self.assertEqual(self.client.get("/api/works/?scope=all").json()[0]["team_name"], details["team_name"])

    def test_award_is_required_for_submission_and_team_photos_are_supplementary(self):
        work = self.draft(award_info="  ")
        address = f"/api/works/{work}/"
        self.assertEqual(self.author.get(address).json()["award_info"], "")
        invalid = self.author.post(address + "assets/", {"file": SimpleUploadedFile("伪装.jpg", b"invalid")})
        self.assertEqual(invalid.status_code, 400)
        photo = self.attachment(work, team_photo())
        photo_path = address + f"assets/{photo}/photo/"
        self.assertEqual(self.viewer.get(photo_path).status_code, 404)
        self.assertEqual(self.author.post(address + "submit/").status_code, 400)
        self.assertEqual(self.author.patch(address, {"award_info": "未获奖"}, content_type="application/json").status_code, 200)
        response = self.author.post(address + "submit/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("作品附件", response.json()["detail"])
        attachment = self.attachment(work, pptx())
        self.publish(work)
        self.assertEqual(Client().get(photo_path).status_code, 403)
        with closing(self.viewer.get(photo_path)) as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/webp")
            self.assertEqual(response["Cache-Control"], "private, no-store")
            with Image.open(BytesIO(b"".join(response.streaming_content))) as image:
                self.assertEqual(image.size, (1600, 800))
                self.assertFalse(image.getexif())
        self.assertEqual(self.viewer.get(address + f"assets/{attachment}/photo/").status_code, 404)
        self.client.patch(f"/api/manage/works/{work}/access/", {"is_visible": False}, content_type="application/json")
        self.assertEqual(self.viewer.get(photo_path).status_code, 404)

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
        self.assertEqual(self.viewer.get(pdf_url + "pdf/layout/").status_code, 404)
        self.assertEqual(self.viewer.get(audio_url + "audio/").status_code, 404)
        self.publish(work)
        layout = self.viewer.get(pdf_url + "pdf/layout/")
        self.assertEqual(layout.status_code, 200)
        self.assertEqual(layout["Cache-Control"], "private, no-store")
        self.assertEqual(layout.json(), {"pages": [[600, 400], [400, 600]]})
        self.assertEqual(self.viewer.get(audio_url + "pdf/layout/").status_code, 404)
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
        self.assertEqual(self.viewer.get(pdf_url + "pdf/layout/").status_code, 404)
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

    def test_management_api_and_legacy_links(self):
        work = self.draft()
        self.attachment(work, pptx())
        self.assertEqual(self.author.post(f"/api/works/{work}/submit/").status_code, 200)
        self.assertEqual(self.viewer.get("/api/works/?scope=all").status_code, 403)
        managed = self.client.get("/api/works/?scope=all").json()[0]
        self.assertEqual(managed["owner_username"], self.owner.username)
        self.assertFalse(managed["allow_download"])
        self.assertNotIn("owner_username", self.author.get(f"/api/works/{work}/").json())
        self.assertRedirects(self.client.get(f"/admin/works/work/{work}/change/"), "/#manage/works", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/admin/auth/user/add/"), "/#manage/accounts", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/admin/auth/group/"), "/#manage", fetch_redirect_response=False)
        self.assertEqual(self.client.post("/admin/auth/group/add/", {"name": "obsolete"}).status_code, 405)
        self.assertEqual(Work.objects.get(pk=work).status, Work.Status.PENDING)
