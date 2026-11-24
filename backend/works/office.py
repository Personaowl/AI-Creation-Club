import time
from urllib.parse import urlencode

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET
from rest_framework.exceptions import APIException

from .files import file_response
from .models import Asset
from .policies import can_view_work

TICKET_SALT = "entrystage.onlyoffice.source"


class OfficeUnavailable(APIException):
    status_code = 503
    default_detail = "PPT 预览服务尚未连接，请联系管理员。"


def office_ready():
    return all((
        settings.ONLYOFFICE_URL, settings.ONLYOFFICE_SOURCE_ORIGIN,
        settings.ONLYOFFICE_BROWSER_SECRET, settings.ONLYOFFICE_OUTBOX_SECRET,
    ))


def source_url(asset_id, ticket):
    query = urlencode({"ticket": ticket})
    endpoint = reverse("office_source", kwargs={"asset_id": asset_id})
    return f"{settings.ONLYOFFICE_SOURCE_ORIGIN}{endpoint}?{query}"


def preview_config(user, asset):
    if not office_ready():
        raise OfficeUnavailable()
    ticket = signing.dumps({"user": user.pk, "asset": str(asset.pk)}, salt=TICKET_SALT)
    config = {
        "type": "desktop",
        "documentType": "slide",
        "width": "100%",
        "height": "100%",
        "document": {
            "url": source_url(asset.pk, ticket),
            "key": "entrystage-" + asset.pk.hex,
            "title": asset.original_name[:128],
            "fileType": asset.extension,
            "permissions": {"edit": False, "download": False, "print": False, "copy": False},
        },
        "editorConfig": {
            "mode": "view",
            "lang": "zh-CN",
            "coEditing": {"mode": "strict", "change": False},
            "user": {"id": str(user.pk), "name": user.get_username()},
        },
    }
    token = jwt.encode(
        {**config, "exp": int(time.time()) + settings.ONLYOFFICE_TICKET_AGE},
        settings.ONLYOFFICE_BROWSER_SECRET,
        algorithm="HS256",
    )
    return {
        "api_url": settings.ONLYOFFICE_URL + "/web-apps/apps/api/documents/api.js",
        "config": {**config, "token": token},
    }


@require_GET
def office_source(request, asset_id):
    if not office_ready():
        raise Http404
    ticket = request.GET.get("ticket", "")
    header = request.headers.get(settings.ONLYOFFICE_OUTBOX_HEADER, "")
    if not ticket or not header.startswith("Bearer "):
        raise Http404
    try:
        claims = jwt.decode(header.removeprefix("Bearer "), settings.ONLYOFFICE_OUTBOX_SECRET, algorithms=["HS256"])
        payload = claims.get("payload")
        if not isinstance(payload, dict) or payload.get("url") != source_url(asset_id, ticket):
            raise Http404
        if claims.get("operation", "download") != "download":
            raise Http404
        scope = signing.loads(ticket, salt=TICKET_SALT, max_age=settings.ONLYOFFICE_TICKET_AGE)
    except (jwt.InvalidTokenError, signing.BadSignature) as error:
        raise Http404 from error
    if not isinstance(scope, dict) or scope.get("asset") != str(asset_id):
        raise Http404
    user = get_object_or_404(get_user_model(), pk=scope.get("user"), is_active=True)
    asset = get_object_or_404(Asset.objects.select_related("work"), pk=asset_id, kind=Asset.Kind.SLIDES)
    if not can_view_work(user, asset.work):
        raise Http404
    return file_response(asset)
