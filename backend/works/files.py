import re
import zipfile
from io import BytesIO
from pathlib import PurePath

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from PIL import Image, ImageOps
from rest_framework import serializers

from .models import Asset
from .pdf_preview import is_readable_pdf

FORMATS = {
    "ppt": (Asset.Kind.SLIDES, "application/vnd.ms-powerpoint"),
    "pptx": (Asset.Kind.SLIDES, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "pdf": (Asset.Kind.PDF, "application/pdf"),
    "mp4": (Asset.Kind.VIDEO, "video/mp4"),
    "webm": (Asset.Kind.VIDEO, "video/webm"),
    "mp3": (Asset.Kind.AUDIO, "audio/mpeg"),
    "zip": (Asset.Kind.SOURCE, "application/zip"),
}
PHOTO_FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
PHOTO_MAX_BYTES = 10 * 1024 * 1024
PHOTO_MAX_PIXELS = 25_000_000
PHOTO_MAX_COUNT = 8
BYTE_RANGE = re.compile(r"bytes=(\d{0,18})-(\d{0,18})")
CHUNK_SIZE = 128 * 1024


def has_mp3_frame(upload, head):
    if head.startswith(b"ID3"):
        if len(head) < 10 or head[3] not in (2, 3, 4) or any(byte >= 128 for byte in head[6:10]):
            return False
        # Each ID3 size byte contributes seven bits.
        tag_size = sum(byte << shift for byte, shift in zip(head[6:10], (21, 14, 7, 0)))
        audio_start = 10 + tag_size + (10 if head[3] == 4 and head[5] & 0x10 else 0)
        upload.seek(audio_start)
        head = upload.read(4)

    return (
        len(head) >= 4 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0
        and (head[1] & 0x18) != 0x08 and (head[1] & 0x06) == 0x02
        and (head[2] & 0xF0) != 0xF0 and (head[2] & 0x0C) != 0x0C
    )


def prepare_upload(upload):
    path = PurePath(upload.name)
    extension = path.suffix.lower().lstrip(".")
    if extension in PHOTO_FORMATS:
        photo = prepare_team_photo(upload, PHOTO_FORMATS[extension], f"{path.stem[:250]}.webp")
        return photo, "webp", Asset.Kind.PHOTO
    if extension not in FORMATS:
        raise serializers.ValidationError({"file": "作品附件支持 PPT、PPTX、PDF、MP4、WebM、MP3 或 ZIP。团队照片支持 JPG、PNG 或 WebP。"})
    if not 0 < upload.size <= settings.UPLOAD_MAX_BYTES:
        raise serializers.ValidationError({"file": "文件为空或超过上传大小限制。"})

    try:
        head = upload.read(12)
        valid = False
        if extension == "ppt":
            valid = head.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
        elif extension == "pdf" and head.startswith(b"%PDF-"):
            upload.seek(0)
            if not is_readable_pdf(upload):
                raise serializers.ValidationError({"file": "PDF 无法读取，请上传未加密且包含页面的 PDF。"})
            valid = True
        elif extension == "mp4":
            valid = head[4:8] == b"ftyp"
        elif extension == "webm":
            valid = head.startswith(bytes.fromhex("1A45DFA3"))
        elif extension == "mp3":
            valid = has_mp3_frame(upload, head)
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
    return upload, extension, FORMATS[extension][0]


def prepare_team_photo(upload, photo_format, name):
    if not 0 < upload.size <= min(settings.UPLOAD_MAX_BYTES, PHOTO_MAX_BYTES):
        raise serializers.ValidationError({"file": "团队照片不能为空，单张最多 10 MB。"})
    try:
        with Image.open(upload, formats=[photo_format]) as image:
            if image.width * image.height > PHOTO_MAX_PIXELS:
                raise serializers.ValidationError({"file": "团队照片不能超过 2500 万像素。"})
            if getattr(image, "is_animated", False):
                raise serializers.ValidationError({"file": "请上传静态团队照片。"})
            with ImageOps.exif_transpose(image) as oriented:
                mode = "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
                with oriented.convert(mode) as photo:
                    photo.thumbnail((1600, 1600))
                    with BytesIO() as output:
                        # Export only pixels so location data and other camera metadata stay private.
                        photo.save(output, format="WEBP", quality=85)
                        return ContentFile(output.getvalue(), name=name)
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as error:
        raise serializers.ValidationError({"file": "团队照片无法读取，请选择有效的 JPG、PNG 或 WebP 图片。"}) from error


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
        content_type="image/webp" if asset.kind == Asset.Kind.PHOTO else FORMATS[asset.extension][1],
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


def media_response(asset, range_header):
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
