from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .files import PHOTO_MAX_COUNT, prepare_upload
from .models import AccessChange, Asset, Review, Work
from .policies import active, can_edit_work, can_revise_work


CONTENT_FIELDS = (
    "title", "description", "competition_id", "competition_name", "team_name", "team_members",
    "team_intro", "award_info", "ip_details",
)


def lock_work(work_id):
    return get_object_or_404(Work.objects.select_for_update(), pk=work_id)


def require_editable(user, work):
    if not can_edit_work(user, work):
        raise PermissionDenied("只有作者可以修改草稿或退回的作品。")


def require_reviewer(user):
    if not active(user) or not user.is_superuser:
        raise PermissionDenied("需要管理员权限。")


@transaction.atomic
def start_revision(user, work_id):
    work = lock_work(work_id)
    if not can_revise_work(user, work):
        raise PermissionDenied("只有作品作者可以修改已通过审核的作品。")
    content = {field: getattr(work, field) for field in CONTENT_FIELDS}
    revision, created = Work.objects.get_or_create(revision_of=work, defaults={"owner_id": work.owner_id, **content})
    if created:
        Asset.objects.bulk_create([
            Asset(work=revision, file=asset.file.name, original_name=asset.original_name,
                  extension=asset.extension, kind=asset.kind, size=asset.size)
            for asset in work.assets.all()
        ])
    return revision


@transaction.atomic
def edit_work(user, work_id, **fields):
    work = lock_work(work_id)
    require_editable(user, work)
    for field, value in fields.items():
        setattr(work, field, value)
    if fields:
        work.save(update_fields=[*fields, "updated_at"])
    return work


def add_asset(user, work_id, upload):
    # Validate without taking a database lock, then check the current state before saving.
    work = get_object_or_404(Work, pk=work_id)
    require_editable(user, work)
    upload, extension, kind = prepare_upload(upload)
    asset = Asset(
        work_id=work_id, original_name=upload.name, extension=extension, kind=kind, size=upload.size,
    )
    try:
        with transaction.atomic():
            work = lock_work(work_id)
            require_editable(user, work)
            if kind == Asset.Kind.PHOTO and work.assets.filter(kind=kind).count() >= PHOTO_MAX_COUNT:
                raise ValidationError({"file": f"每件作品最多添加 {PHOTO_MAX_COUNT} 张团队照片。"})
            asset.file.save(upload.name, upload, save=False)
            asset.save()
            work.save(update_fields=["updated_at"])
    except Exception:
        if asset.file.name:
            asset.file.storage.delete(asset.file.name)
        raise
    return asset


@transaction.atomic
def remove_asset(user, work_id, asset_id):
    work = lock_work(work_id)
    require_editable(user, work)
    asset = get_object_or_404(Asset, work=work, pk=asset_id)
    remove_asset_record(asset)
    work.save(update_fields=["updated_at"])


def remove_asset_record(asset):
    storage, name = asset.file.storage, asset.file.name
    asset.delete()

    def remove_file():
        # A draft and its published work can share the same stored attachment.
        if not Asset.objects.filter(file=name).exists():
            storage.delete(name)

    transaction.on_commit(remove_file, robust=True)


@transaction.atomic
def submit_work(user, work_id):
    work = lock_work(work_id)
    require_editable(user, work)
    if not work.award_info.strip():
        raise ValidationError({"detail": "请填写获奖情况，未获奖或评审中也可以填写。"})
    if not work.assets.exclude(kind=Asset.Kind.PHOTO).exists():
        raise ValidationError({"detail": "请先给作品添加至少一个作品附件。"})
    work.status = Work.Status.PENDING
    work.review_note = ""
    work.save(update_fields=["status", "review_note", "updated_at"])
    return work


@transaction.atomic
def withdraw_work(user, work_id):
    work = lock_work(work_id)
    if not active(user) or work.owner_id != user.pk:
        raise PermissionDenied("只有作品作者可以撤回投稿。")
    if work.status != Work.Status.PENDING:
        raise ValidationError({"detail": "只有待审核的投稿可以撤回。"})
    work.status = Work.Status.DRAFT
    work.save(update_fields=["status", "updated_at"])
    return work


@transaction.atomic
def review_work(user, work_id, decision, note=""):
    require_reviewer(user)
    work = lock_work(work_id)
    if work.status != Work.Status.PENDING:
        raise ValidationError({"detail": "只有待审核的作品可以审核。"})
    if decision not in (Work.Status.APPROVED, Work.Status.REJECTED):
        raise ValidationError({"decision": "请选择通过或退回。"})
    if decision == Work.Status.REJECTED and not note.strip():
        raise ValidationError({"note": "退回时请填写原因。"})
    note = note.strip()
    if work.revision_of_id and decision == Work.Status.APPROVED:
        return approve_revision(work, user, note)

    work.status = decision
    work.review_note = note
    work.save(update_fields=["status", "review_note", "updated_at"])
    Review.objects.create(
        work_id=work.revision_of_id or work.pk, reviewer=user, decision=decision,
        note=note, is_revision=work.revision_of_id is not None,
    )
    return work


def approve_revision(revision, reviewer, note):
    work = lock_work(revision.revision_of_id)
    for field in CONTENT_FIELDS:
        setattr(work, field, getattr(revision, field))
    work.review_note = note
    work.save(update_fields=[*CONTENT_FIELDS, "review_note", "updated_at"])

    removed = {asset.file.name: asset for asset in work.assets.all()}
    for asset in revision.assets.all():
        if removed.pop(asset.file.name, None) is None:
            asset.work = work
            asset.save(update_fields=["work"])
    for asset in removed.values():
        remove_asset_record(asset)
    Review.objects.create(work=work, reviewer=reviewer, decision=Work.Status.APPROVED, note=note, is_revision=True)
    revision.delete()
    return work


@transaction.atomic
def change_access(user, work_id, **fields):
    require_reviewer(user)
    work = lock_work(work_id)
    if work.status != Work.Status.APPROVED:
        raise ValidationError({"detail": "通过审核后才能设置上架与下载。"})
    if "competition" in fields:
        competition = fields.pop("competition")
        fields["competition_id"] = competition.pk if competition else None
        fields["competition_name"] = competition.name if competition else ""
    changes = {field: value for field, value in fields.items() if getattr(work, field) != value}
    for field, value in changes.items():
        setattr(work, field, value)
    if changes:
        work.save(update_fields=[*changes, "updated_at"])
    if "is_visible" in changes or "allow_download" in changes:
        AccessChange.objects.create(
            work=work, actor=user, is_visible=work.is_visible, allow_download=work.allow_download,
        )
    return work


@transaction.atomic
def add_comment(user, work_id, body):
    work = lock_work(work_id)
    if not active(user) or not work.published:
        raise NotFound()
    return work.comments.create(author=user, body=body)


@transaction.atomic
def delete_comment(user, work_id, comment_id):
    work = lock_work(work_id)
    if not active(user) or not work.published:
        raise NotFound()
    comment = get_object_or_404(work.comments, pk=comment_id)
    if not (user.is_superuser or comment.author_id == user.pk):
        raise PermissionDenied("只有评论作者或管理员可以删除此评论。")
    comment.delete()
