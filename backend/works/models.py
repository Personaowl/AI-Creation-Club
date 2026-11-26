import uuid

from django.conf import settings
from django.db import models


class Competition(models.Model):
    name = models.CharField("比赛名称", max_length=120)
    name_key = models.CharField(max_length=360, unique=True, editable=False)

    class Meta:
        ordering = ["name", "id"]


class Work(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已退回"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="works")
    revision_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.CASCADE, related_name="revision")
    title = models.CharField("作品名称", max_length=120)
    description = models.TextField("作品简介", max_length=3000, blank=True)
    competition_name = models.CharField("比赛名称", max_length=120, blank=True)
    competition = models.ForeignKey(Competition, null=True, blank=True, on_delete=models.PROTECT, related_name="works")
    team_name = models.CharField("团队名称", max_length=120, blank=True)
    team_members = models.TextField("团队成员", max_length=600, blank=True)
    team_intro = models.TextField("团队简介", max_length=1200, blank=True)
    award_info = models.CharField("获奖情况", max_length=200, blank=True)
    ip_details = models.TextField("知识产权情况", max_length=1200, blank=True)
    status = models.CharField("审核状态", max_length=10, choices=Status.choices, default=Status.DRAFT)
    is_visible = models.BooleanField("上架展示", default=False)
    allow_download = models.BooleanField("允许成员下载原件", default=False)
    review_note = models.TextField("审核意见", blank=True, max_length=1000)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["status", "is_visible", "-updated_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status="approved") | models.Q(is_visible=False, allow_download=False),
                name="work_access_requires_approval",
            ),
            models.CheckConstraint(
                condition=models.Q(revision_of__isnull=True) | ~models.Q(status="approved"),
                name="revision_approval_updates_original",
            ),
        ]
        verbose_name = "竞赛作品"
        verbose_name_plural = "竞赛作品"

    def __str__(self):
        return self.title

    @property
    def published(self):
        return self.status == self.Status.APPROVED and self.is_visible


def work_file_path(asset, filename):
    return f"works/{asset.work_id}/{asset.pk.hex}.{asset.extension}"


class Asset(models.Model):
    class Kind(models.TextChoices):
        SLIDES = "slides", "演示文稿"
        PDF = "pdf", "PDF 文档"
        VIDEO = "video", "视频"
        AUDIO = "audio", "音频"
        SOURCE = "source", "源码附件"
        PHOTO = "photo", "团队照片"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="assets")
    file = models.FileField(upload_to=work_file_path)
    original_name = models.CharField("文件名", max_length=255)
    extension = models.CharField(max_length=4)
    kind = models.CharField("文件类型", max_length=8, choices=Kind.choices)
    size = models.PositiveBigIntegerField("文件大小")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "作品附件"
        verbose_name_plural = "作品附件"

    def __str__(self):
        return self.original_name


class Review(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=10, choices=Work.Status.choices)
    note = models.TextField(blank=True, max_length=1000)
    is_revision = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "审核记录"
        verbose_name_plural = "审核记录"


class AccessChange(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="access_changes")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    is_visible = models.BooleanField("上架展示")
    allow_download = models.BooleanField("允许成员下载原件")
    created_at = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "作品权限记录"
        verbose_name_plural = "作品权限记录"


class WorkComment(models.Model):
    work = models.ForeignKey(Work, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["work", "-id"])]
