from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction

User = get_user_model()


def validate_password(password, user):
    password_validation.validate_password(password, user)


@transaction.atomic
def reclaim_member(user):
    member = User.objects.select_for_update().get(pk=user.pk)
    if member.is_staff or member.is_superuser:
        raise ValidationError("只能回收普通成员账号。")
    if member.is_active or member.has_usable_password():
        member.is_active = False
        member.set_unusable_password()
        member.save(update_fields=["is_active", "password"])
    return member


@transaction.atomic
def reset_member(user, password, reactivate=False):
    member = User.objects.select_for_update().get(pk=user.pk)
    if member.is_staff or member.is_superuser:
        raise ValidationError("只能重设普通成员账号。")
    validate_password(password, member)
    member.set_password(password)
    if reactivate:
        member.is_active = True
    member.save(update_fields=["password", "is_active"])
    return member
