from secrets import token_hex

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.crypto import salted_hmac

from .models import IssuedMemberPassword

User = get_user_model()
PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def validate_password(password, user):
    password_validation.validate_password(password, user)


def issued_password(nonce):
    # A stored nonce reproduces an issued password only with the deployment secret.
    digest = salted_hmac("accounts.issued-member-password.v1", nonce, algorithm="sha256").digest()
    value = int.from_bytes(digest, "big")
    characters = []
    for _ in range(8):
        value, index = divmod(value, len(PASSWORD_ALPHABET))
        characters.append(PASSWORD_ALPHABET[index])
    return "".join(characters)


def generate_issued_password(user):
    for _ in range(64):
        nonce = token_hex(32)
        password = issued_password(nonce)
        try:
            validate_password(password, user)
        except ValidationError:
            continue
        return password, nonce
    raise ValidationError("无法生成符合密码规则的 8 位初始密码。")


def generate_initial_password(user):
    return generate_issued_password(user)[0]


def read_issued_password(member):
    if member.is_active:
        issued = IssuedMemberPassword.objects.filter(member=member).first()
        if issued:
            password = issued_password(issued.nonce)
            if check_password(password, member.password):
                return password
    return None


def clear_issued_password(member):
    IssuedMemberPassword.objects.filter(member=member).delete()


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
    clear_issued_password(member)
    return member


def save_member_password(member, password=None, reactivate=False):
    generated = nonce = None
    if password is None:
        generated, nonce = generate_issued_password(member)
        password = generated
    else:
        validate_password(password, member)
    member.set_password(password)
    if reactivate:
        member.is_active = True
    if member.pk is None:
        member.save()
    else:
        member.save(update_fields=["password", "is_active"])
    if nonce and member.is_active:
        IssuedMemberPassword.objects.update_or_create(member=member, defaults={"nonce": nonce})
    else:
        clear_issued_password(member)
    return member, generated


@transaction.atomic
def create_member(username, password=None):
    return save_member_password(User(username=username), password)


@transaction.atomic
def reset_member(user, password=None, reactivate=False):
    return save_member_password(lock_member(user), password, reactivate)


@transaction.atomic
def reissue_member(user):
    member = lock_member(user)
    if member.is_active:
        return member, None
    return save_member_password(member, reactivate=True)
