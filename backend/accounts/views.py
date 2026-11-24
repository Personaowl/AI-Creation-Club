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

from .services import reclaim_member, reset_member, validate_password

User = get_user_model()


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and request.user.is_superuser)


class Credentials(serializers.Serializer):
    username = serializers.CharField(max_length=150, validators=User._meta.get_field("username").validators)
    password = serializers.CharField(trim_whitespace=False, max_length=256, write_only=True)


class NewPassword(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, max_length=256, write_only=True)


def user_data(user):
    return {
        "id": user.pk,
        "username": user.get_username(),
        "is_admin": user.is_superuser,
        "is_active": user.is_active,
    }


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
    user = request.user
    if not user.check_password(payload.validated_data["current_password"]):
        raise serializers.ValidationError({"current_password": "当前密码不正确。"})
    password = payload.validated_data["password"]
    try:
        validate_password(password, user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"password": error.messages}) from error
    user.set_password(password)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)
    return session_data(request, user)


@api_view(["GET", "POST"])
@permission_classes([IsAdministrator])
def members(request):
    if request.method == "GET":
        users = User.objects.filter(is_staff=False, is_superuser=False).order_by("username")
        return Response([user_data(user) for user in users])

    payload = Credentials(data=request.data)
    payload.is_valid(raise_exception=True)
    user = User(username=payload.validated_data["username"])
    try:
        validate_password(payload.validated_data["password"], user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"password": error.messages}) from error
    try:
        with transaction.atomic():
            user.set_password(payload.validated_data["password"])
            user.save()
    except IntegrityError as error:
        raise serializers.ValidationError({"username": "该账号名已存在。"}) from error
    return Response(user_data(user), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAdministrator])
def reclaim(request, user_id):
    user = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    return Response(user_data(reclaim_member(user)))


@api_view(["POST"])
@permission_classes([IsAdministrator])
def reset_password(request, user_id):
    class ResetPassword(NewPassword):
        reactivate = serializers.BooleanField(default=False)

    user = get_object_or_404(User, pk=user_id, is_staff=False, is_superuser=False)
    payload = ResetPassword(data=request.data)
    payload.is_valid(raise_exception=True)
    try:
        user = reset_member(user, **payload.validated_data)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"password": error.messages}) from error
    return Response(user_data(user))
