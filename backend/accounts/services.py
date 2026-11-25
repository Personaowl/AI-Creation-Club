from secrets import choice

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction

User = get_user_model()
PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def validate_password(password, user):
    password_validation.validate_password(password, user)


def generate_initial_password(user):
    for _ in range(64):
        password = "".join(choice(PASSWORD_ALPHABET) for _ in range(8))
        try:
            validate_password(password, user)
        except ValidationError:
            continue
        return password
    raise ValidationError("无法生成符合密码规则的 8 位初始密码。")


def lock_member(user):
    member = User.objects.select_for_update().get(pk=user.pk)
    if member.is_staff or member.is_superuser:
        raise ValidationError("只能操作普通成员账号。")
    return member


@transaction.atomic
def reclaim_member(user):
    member = lock_member(user)
    if member.is_active or member.has_usable_password():
        member.is_active = False
        member.set_unusable_password()
        member.save(update_fields=["is_active", "password"])
    return member


def save_member_password(member, password, reactivate):
    member.set_password(password)
    if reactivate:
        member.is_active = True
    member.save(update_fields=["password", "is_active"])


@transaction.atomic
def reset_member(user, password=None, reactivate=False):
    member = lock_member(user)
    generated = None
    if password is None:
        generated = password = generate_initial_password(member)
    else:
        validate_password(password, member)
    save_member_password(member, password, reactivate)
    return member, generated


@transaction.atomic
def reissue_member(user):
    member = lock_member(user)
    if member.is_active:
        return member, None
    password = generate_initial_password(member)
    save_member_password(member, password, reactivate=True)
    return member, password
