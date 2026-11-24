from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from .files import validate_upload
from .models import AccessChange, Asset, Review, Work
from .policies import active, can_edit_work


def lock_work(work_id):
    return get_object_or_404(Work.objects.select_for_update(), pk=work_id)


def require_editable(user, work):
    if not can_edit_work(user, work):
        raise PermissionDenied("只有作者可以修改草稿或退回的作品。")


def require_reviewer(user):
    if not active(user) or not user.is_superuser:
        raise PermissionDenied("需要管理员权限。")


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
    extension, kind = validate_upload(upload)
    asset = Asset(
        work_id=work_id, original_name=upload.name, extension=extension, kind=kind, size=upload.size,
    )
    try:
        with transaction.atomic():
            work = lock_work(work_id)
            require_editable(user, work)
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
    storage, name = asset.file.storage, asset.file.name
    asset.delete()
    work.save(update_fields=["updated_at"])
    transaction.on_commit(lambda: storage.delete(name), robust=True)


@transaction.atomic
def submit_work(user, work_id):
    work = lock_work(work_id)
    require_editable(user, work)
    if not work.assets.exists():
        raise ValidationError({"detail": "请先给作品添加至少一个文件。"})
    work.status = Work.Status.PENDING
    work.review_note = ""
    work.save(update_fields=["status", "review_note", "updated_at"])
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
    work.status = decision
    work.review_note = note.strip()
    work.save(update_fields=["status", "review_note", "updated_at"])
    Review.objects.create(work=work, reviewer=user, decision=decision, note=work.review_note)
    return work


@transaction.atomic
def change_access(user, work_id, **fields):
    require_reviewer(user)
    work = lock_work(work_id)
    if work.status != Work.Status.APPROVED:
        raise ValidationError({"detail": "通过审核后才能设置上架与下载。"})
    changes = {field: value for field, value in fields.items() if getattr(work, field) != value}
    for field, value in changes.items():
        setattr(work, field, value)
    if changes:
        work.save(update_fields=[*changes, "updated_at"])
        AccessChange.objects.create(
            work=work, actor=user, is_visible=work.is_visible, allow_download=work.allow_download,
        )
    return work
