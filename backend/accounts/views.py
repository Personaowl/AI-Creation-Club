from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response

from .services import (
    clear_issued_password, create_member, read_issued_password, reclaim_member, reissue_member,
    reset_member, validate_password,
)

User = get_user_model()


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and request.user.is_superuser)


class Credentials(serializers.Serializer):
    username = serializers.CharField(max_length=150, validators=User._meta.get_field("username").validators)
    password = serializers.CharField(trim_whitespace=False, max_length=256, write_only=True)


class NewPassword(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, max_length=256, write_only=True)


class NewMember(Credentials):
    password = serializers.CharField(trim_whitespace=False, max_length=256, write_only=True, required=False)


class ResetPassword(NewPassword):
    password = serializers.CharField(trim_whitespace=False, max_length=256, write_only=True, required=False)
    reactivate = serializers.BooleanField(default=False)


def user_data(user):
    return {
        "id": user.pk,
        "username": user.get_username(),
        "is_admin": user.is_superuser,
        "is_active": user.is_active,
    }


def member_data(user):
    return {**user_data(user), "date_joined": user.date_joined, "last_login": user.last_login}


def member_response(user, generated=None, status_code=status.HTTP_200_OK):
    data = member_data(user)
    if generated is not None:
        data["initial_password"] = generated
    return Response(data, status=status_code, headers={"Cache-Control": "no-store"})


def session_data(request, user):
    response = Response({"user": user_data(user) if user.is_authenticated else None, "csrf_token": get_token(request)})
    response["Cache-Control"] = "no-store"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def session_view(request):
    return session_data(request, request.user)


@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def login_view(request):
    payload = Credentials(data=request.data)
    payload.is_valid(raise_exception=True)
    user = authenticate(request, **payload.validated_data)
    if user is None:
        return Response({"detail": "账号或密码无效。"}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, user)
    return session_data(request, user)


@api_view(["POST"])
def logout_view(request):
    logout(request)
    return session_data(request, request.user)


@api_view(["POST"])
def change_password(request):
    class PasswordChange(NewPassword):
        current_password = serializers.CharField(trim_whitespace=False, max_length=256, write_only=True)

    payload = PasswordChange(data=request.data)
    payload.is_valid(raise_exception=True)
    password = payload.validated_data["password"]
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or not user.check_password(payload.validated_data["current_password"]):
            raise serializers.ValidationError({"current_password": "当前密码不正确。"})
        try:
            validate_password(password, user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        user.set_password(password)
        user.save(update_fields=["password"])
        clear_issued_password(user)
    update_session_auth_hash(request, user)
    return session_data(request, user)


@api_view(["GET", "POST"])
@permission_classes([IsAdministrator])
def members(request):
    if request.method == "GET":
        users = User.objects.filter(is_staff=False, is_superuser=False).order_by("username")
        return Response([member_data(user) for user in users])

    payload = NewMember(data=request.data)
    payload.is_valid(raise_exception=True)
    try:
        user, generated = create_member(**payload.validated_data)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"password": error.messages}) from error
    except IntegrityError as error:
        raise serializers.ValidationError({"username": "该账号名已存在。"}) from error
    return member_response(user, generated, status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAdministrator])
def member_issued_password(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    return Response({"initial_password": read_issued_password(user)}, headers={"Cache-Control": "private, no-store"})


@api_view(["POST"])
@permission_classes([IsAdministrator])
def reclaim(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    return member_response(reclaim_member(user))


@api_view(["POST"])
@permission_classes([IsAdministrator])
def reissue(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    try:
        user, generated = reissue_member(user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"detail": error.messages[0]}) from error
    if generated is None:
        raise serializers.ValidationError({"detail": "只有已回收的账号可以重新发放。"})
    return member_response(user, generated)


@api_view(["POST"])
@permission_classes([IsAdministrator])
def reset_password(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    payload = ResetPassword(data=request.data)
    payload.is_valid(raise_exception=True)
    try:
        user, generated = reset_member(user, **payload.validated_data)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"password": error.messages}) from error
    return member_response(user, generated)
