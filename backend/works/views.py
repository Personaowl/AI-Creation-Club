from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from accounts.views import IsAdministrator

from . import services
from .files import file_response, private_response, video_response
from .models import Asset, Work
from .office import OfficeUnavailable, preview_config
from .policies import can_download_work, can_view_work
from .serializers import AccessSerializer, AssetSerializer, ReviewSerializer, WorkSerializer, WorkWriteSerializer


def work_data(request, work):
    return WorkSerializer(work, context={"request": request}).data


def visible_work(request, work_id):
    work = get_object_or_404(Work.objects.prefetch_related("assets"), pk=work_id)
    if not can_view_work(request.user, work):
        raise NotFound()
    return work


def visible_asset(request, work_id, asset_id):
    asset = get_object_or_404(Asset.objects.select_related("work"), pk=asset_id, work_id=work_id)
    if not can_view_work(request.user, asset.work):
        raise NotFound()
    return asset


@api_view(["GET", "POST"])
def work_list(request):
    if request.method == "POST":
        payload = WorkWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        work = payload.save(owner=request.user)
        return Response(work_data(request, work), status=status.HTTP_201_CREATED)

    records = Work.objects.prefetch_related("assets")
    match request.query_params.get("scope", "gallery"):
        case "gallery":
            records = records.filter(status=Work.Status.APPROVED, is_visible=True)
        case "mine":
            records = records.filter(owner=request.user)
        case "review":
            if not request.user.is_superuser:
                raise PermissionDenied()
            records = records.filter(status=Work.Status.PENDING)
        case "all":
            if not request.user.is_superuser:
                raise PermissionDenied()
        case _:
            raise serializers.ValidationError({"scope": "未知的作品范围。"})
    return Response(WorkSerializer(records, many=True, context={"request": request}).data)


@api_view(["GET", "PATCH"])
def work_detail(request, work_id):
    work = visible_work(request, work_id)
    if request.method == "PATCH":
        payload = WorkWriteSerializer(work, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        work = services.edit_work(request.user, work.id, **payload.validated_data)
    return Response(work_data(request, work))


@api_view(["POST"])
def upload(request, work_id):
    class UploadSerializer(serializers.Serializer):
        file = serializers.FileField(max_length=255)

    visible_work(request, work_id)
    payload = UploadSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    asset = services.add_asset(request.user, work_id, payload.validated_data["file"])
    return Response(AssetSerializer(asset).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
def delete_asset(request, work_id, asset_id):
    visible_asset(request, work_id, asset_id)
    services.remove_asset(request.user, work_id, asset_id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def submit(request, work_id):
    visible_work(request, work_id)
    return Response(work_data(request, services.submit_work(request.user, work_id)))


@api_view(["POST"])
@permission_classes([IsAdministrator])
def review(request, work_id):
    payload = ReviewSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    return Response(work_data(request, services.review_work(request.user, work_id, **payload.validated_data)))


@api_view(["PATCH"])
@permission_classes([IsAdministrator])
def access(request, work_id):
    payload = AccessSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    return Response(work_data(request, services.change_access(request.user, work_id, **payload.validated_data)))


@api_view(["GET"])
def download(request, work_id, asset_id):
    asset = visible_asset(request, work_id, asset_id)
    if not can_download_work(request.user, asset.work):
        raise PermissionDenied("此作品未开放原件下载。")
    return file_response(asset, attachment=True)


@api_view(["GET"])
def video(request, work_id, asset_id):
    asset = visible_asset(request, work_id, asset_id)
    if asset.kind != Asset.Kind.VIDEO:
        raise NotFound()
    return video_response(asset, request.headers.get("Range"))


@api_view(["GET"])
def presentation(request, work_id, asset_id):
    asset = visible_asset(request, work_id, asset_id)
    if asset.kind != Asset.Kind.SLIDES:
        raise NotFound()
    return private_response(Response(preview_config(request.user, asset)))


@require_GET
@xframe_options_sameorigin
def office_viewer(request, work_id, asset_id):
    asset = get_object_or_404(Asset.objects.select_related("work"), pk=asset_id, work_id=work_id, kind=Asset.Kind.SLIDES)
    if not can_view_work(request.user, asset.work):
        raise Http404
    context = {"title": asset.original_name}
    try:
        context["viewer"] = preview_config(request.user, asset)
    except OfficeUnavailable as error:
        context["message"] = error.default_detail
    return private_response(render(request, "works/office_viewer.html", context, status=200 if "viewer" in context else 503))
