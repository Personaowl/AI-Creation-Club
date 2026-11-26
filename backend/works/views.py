from unicodedata import normalize

from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from accounts.views import IsAdministrator

from . import services
from .files import file_response, media_response, open_asset, private_response
from .models import Asset, Competition, Work
from .office import OfficeUnavailable, preview_config
from .pdf_preview import pdf_page_sizes, render_pdf_page
from .policies import can_download_work, can_view_work
from .serializers import (
    AccessSerializer, AssetSerializer, CommentSerializer, CompetitionSerializer, ManagedWorkSerializer,
    ReviewSerializer, WorkSerializer, WorkWriteSerializer,
)


COMMENT_PAGE_SIZE = 20


def work_data(request, work, managed=False):
    serializer = ManagedWorkSerializer if managed else WorkSerializer
    return serializer(work, context={"request": request}).data


def visible_work(request, work_id):
    work = get_object_or_404(Work.objects.select_related("competition", "revision").prefetch_related("assets"), pk=work_id)
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

    records = Work.objects.select_related("competition", "revision").prefetch_related("assets")
    scope = request.query_params.get("scope", "gallery")
    serializer = WorkSerializer
    match scope:
        case "gallery":
            records = records.filter(status=Work.Status.APPROVED, is_visible=True, revision_of__isnull=True)
        case "mine":
            records = records.filter(owner=request.user, revision_of__isnull=True)
        case "review" | "all":
            if not request.user.is_superuser:
                raise PermissionDenied()
            records = records.select_related("owner")
            serializer = ManagedWorkSerializer
            if scope == "review":
                records = records.filter(status=Work.Status.PENDING)
        case _:
            raise serializers.ValidationError({"scope": "未知的作品范围。"})
    return Response(serializer(records, many=True, context={"request": request}).data)


@api_view(["GET"])
def competition_list(request):
    return Response(CompetitionSerializer(Competition.objects.all(), many=True).data)


def save_competition(payload):
    payload.is_valid(raise_exception=True)
    name = payload.validated_data["name"]
    key = normalize("NFC", name.casefold())
    try:
        with transaction.atomic():
            return payload.save(name_key=key)
    except IntegrityError:
        if Competition.objects.filter(name_key=key).exists():
            raise serializers.ValidationError({"name": "这个比赛分类已存在。"}) from None
        raise


@api_view(["POST"])
@permission_classes([IsAdministrator])
def create_competition(request):
    payload = CompetitionSerializer(data=request.data)
    save_competition(payload)
    return Response(payload.data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAdministrator])
@transaction.atomic
def manage_competition(request, competition_id):
    competition = get_object_or_404(Competition.objects.select_for_update(), pk=competition_id)
    works = Work.objects.filter(competition=competition)
    if request.method == "DELETE":
        works.update(competition=None, competition_name="")
        competition.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    previous_name = competition.name
    payload = CompetitionSerializer(competition, data=request.data)
    updated = save_competition(payload)
    if updated.name != previous_name:
        works.update(competition_name=updated.name)
    return Response(payload.data)


@api_view(["GET", "POST"])
def comments(request, work_id):
    context = {"request": request}
    if request.method == "POST":
        payload = CommentSerializer(data=request.data, context=context)
        payload.is_valid(raise_exception=True)
        comment = services.add_comment(request.user, work_id, payload.validated_data["body"])
        return private_response(Response(CommentSerializer(comment, context=context).data, status=status.HTTP_201_CREATED))

    work = get_object_or_404(Work, pk=work_id, status=Work.Status.APPROVED, is_visible=True)
    records = work.comments.select_related("author")
    if (before := request.query_params.get("before")) is not None:
        cursor = serializers.IntegerField(min_value=1, max_value=9223372036854775807).run_validation(before)
        records = records.filter(pk__lt=cursor)
    results = list(records[:COMMENT_PAGE_SIZE + 1])
    page = results[:COMMENT_PAGE_SIZE]
    return private_response(Response({
        "items": CommentSerializer(page, many=True, context=context).data,
        "next_before": page[-1].pk if len(results) > COMMENT_PAGE_SIZE else None,
    }))


@api_view(["DELETE"])
def delete_comment(request, work_id, comment_id):
    services.delete_comment(request.user, work_id, comment_id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET", "PATCH"])
def work_detail(request, work_id):
    work = visible_work(request, work_id)
    if request.method == "PATCH":
        payload = WorkWriteSerializer(work, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        work = services.edit_work(request.user, work.id, **payload.validated_data)
    return Response(work_data(request, work))


@api_view(["POST"])
def start_revision(request, work_id):
    visible_work(request, work_id)
    return Response(work_data(request, services.start_revision(request.user, work_id)))


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
def withdraw(request, work_id):
    visible_work(request, work_id)
    return Response(work_data(request, services.withdraw_work(request.user, work_id)))


@api_view(["POST"])
@permission_classes([IsAdministrator])
def review(request, work_id):
    payload = ReviewSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    return Response(work_data(request, services.review_work(request.user, work_id, **payload.validated_data), managed=True))


@api_view(["PATCH"])
@permission_classes([IsAdministrator])
def access(request, work_id):
    payload = AccessSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    return Response(work_data(request, services.change_access(request.user, work_id, **payload.validated_data), managed=True))


@api_view(["DELETE"])
@permission_classes([IsAdministrator])
def delete_work(request, work_id):
    services.delete_work(request.user, work_id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def download(request, work_id, asset_id):
    asset = visible_asset(request, work_id, asset_id)
    if asset.kind == Asset.Kind.PHOTO:
        raise NotFound()
    if not can_download_work(request.user, asset.work):
        raise PermissionDenied("此作品未开放原件下载。")
    return file_response(asset, attachment=True)


@api_view(["GET"])
def photo(request, work_id, asset_id):
    asset = visible_asset(request, work_id, asset_id)
    if asset.kind != Asset.Kind.PHOTO:
        raise NotFound()
    return file_response(asset)


@api_view(["GET"])
def media(request, work_id, asset_id, kind):
    asset = visible_asset(request, work_id, asset_id)
    if asset.kind != kind:
        raise NotFound()
    return media_response(asset, request.headers.get("Range"))


@api_view(["GET"])
def pdf_layout(request, work_id, asset_id):
    asset = visible_asset(request, work_id, asset_id)
    if asset.kind != Asset.Kind.PDF:
        raise NotFound()
    with open_asset(asset) as source:
        sizes = pdf_page_sizes(source)
    if not sizes:
        raise NotFound("PDF 无法读取。")
    return private_response(Response({"pages": sizes}))


@api_view(["GET"])
def pdf_page(request, work_id, asset_id, page):
    asset = visible_asset(request, work_id, asset_id)
    if asset.kind != Asset.Kind.PDF:
        raise NotFound()
    with open_asset(asset) as source:
        result = render_pdf_page(source, page)
    if result is None:
        raise NotFound("PDF 页面无法读取或不存在。")
    image, count = result
    response = HttpResponse(image, content_type="image/png")
    response["X-Page-Count"] = str(count)
    return private_response(response)


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
