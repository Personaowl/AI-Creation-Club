import re
import zipfile
from pathlib import PurePath

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from rest_framework import serializers

from .models import Asset

FORMATS = {
    "ppt": (Asset.Kind.SLIDES, "application/vnd.ms-powerpoint"),
    "pptx": (Asset.Kind.SLIDES, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "mp4": (Asset.Kind.VIDEO, "video/mp4"),
    "webm": (Asset.Kind.VIDEO, "video/webm"),
    "zip": (Asset.Kind.SOURCE, "application/zip"),
}
BYTE_RANGE = re.compile(r"bytes=(\d{0,18})-(\d{0,18})")
CHUNK_SIZE = 128 * 1024


def validate_upload(upload):
    extension = PurePath(upload.name).suffix.lower().lstrip(".")
    if extension not in FORMATS:
        raise serializers.ValidationError({"file": "支持 PPT、PPTX、MP4、WebM 或 ZIP。"})
    if not 0 < upload.size <= settings.UPLOAD_MAX_BYTES:
        raise serializers.ValidationError({"file": "文件为空或超过上传大小限制。"})

    try:
        head = upload.read(12)
        valid = False
        if extension == "ppt":
            valid = head.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
        elif extension == "mp4":
            valid = head[4:8] == b"ftyp"
        elif extension == "webm":
            valid = head.startswith(bytes.fromhex("1A45DFA3"))
        elif extension == "zip":
            valid = zipfile.is_zipfile(upload)
        elif extension == "pptx":
            with zipfile.ZipFile(upload) as archive:
                valid = all(name in archive.NameToInfo for name in ("[Content_Types].xml", "ppt/presentation.xml"))
    except (zipfile.BadZipFile, OSError):
        valid = False
    finally:
        upload.seek(0)
    if not valid:
        raise serializers.ValidationError({"file": "文件内容与所选格式不符。"})
    return extension, FORMATS[extension][0]


def open_asset(asset):
    try:
        return asset.file.storage.open(asset.file.name, "rb")
    except FileNotFoundError as error:
        raise Http404("该文件已不可用。") from error


def private_response(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def file_response(asset, attachment=False):
    return private_response(FileResponse(
        open_asset(asset),
        as_attachment=attachment,
        filename=asset.original_name,
        content_type=FORMATS[asset.extension][1],
    ))


def range_bounds(value, size):
    match = BYTE_RANGE.fullmatch(value)
    if not match:
        return None
    first, last = match.groups()
    if not first:
        if not last or int(last) == 0:
            return None
        return max(0, size - int(last)), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    return (start, end) if start <= end else None


class FileSlice:
    def __init__(self, file, start, length):
        self.file = file
        self.remaining = length
        file.seek(start)

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining == 0:
            raise StopIteration
        chunk = self.file.read(min(CHUNK_SIZE, self.remaining))
        if not chunk:
            raise StopIteration
        self.remaining -= len(chunk)
        return chunk

    def close(self):
        self.file.close()


def video_response(asset, range_header):
    if not range_header:
        response = file_response(asset)
        response["Accept-Ranges"] = "bytes"
        return response

    bounds = range_bounds(range_header, asset.size)
    if not bounds:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{asset.size}"
    else:
        start, end = bounds
        length = end - start + 1
        response = StreamingHttpResponse(
            FileSlice(open_asset(asset), start, length),
            status=206,
            content_type=FORMATS[asset.extension][1],
        )
        response["Content-Length"] = str(length)
        response["Content-Range"] = f"bytes {start}-{end}/{asset.size}"
    response["Accept-Ranges"] = "bytes"
    return private_response(response)
