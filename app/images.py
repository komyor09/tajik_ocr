"""Reading an uploaded image: size limit (413), type check (415), decoding."""

import io

import numpy as np
from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageOps

# Image formats the service accepts. The format is checked by the file content: some clients
# (curl for .webp, many HTTP libraries) send images as application/octet-stream.
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}
GENERIC_TYPES = {None, "", "application/octet-stream"}
MAX_PIXELS = 40_000_000  # ~ 7300x5500; protects the small server from "decompression bomb" images
CHUNK = 1024 * 1024

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


async def read_upload(file: UploadFile, max_mb: int) -> bytes:
    """Read the file in chunks and stop as soon as it is over the limit."""
    declared = file.content_type
    if declared not in GENERIC_TYPES and not declared.startswith("image/"):
        raise HTTPException(status_code=415, detail=f"{file.filename}: тип {declared!r} — не изображение")
    limit = max_mb * 1024 * 1024
    data = bytearray()
    while chunk := await file.read(CHUNK):
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"{file.filename}: файл больше {max_mb} МБ")
    if not data:
        raise HTTPException(status_code=400, detail=f"{file.filename}: пустой файл")
    return bytes(data)


def decode_image(data: bytes, filename: str | None) -> tuple[np.ndarray, int, int]:
    """Bytes -> BGR array (phone EXIF rotation applied), width, height."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=415,
                detail=f"{filename}: формат {img.format} не поддерживается; "
                f"допустимо: {', '.join(sorted(ALLOWED_FORMATS))}",
            )
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Image.DecompressionBombError:
        raise HTTPException(status_code=413, detail=f"{filename}: больше {MAX_PIXELS:,} пикселей") from None
    except OSError:  # includes UnidentifiedImageError
        raise HTTPException(status_code=415, detail=f"{filename}: файл не читается как изображение") from None
    rgb = np.asarray(img)
    return rgb[:, :, ::-1].copy(), img.width, img.height


async def load_upload(file: UploadFile, max_mb: int) -> tuple[np.ndarray, int, int]:
    """Uploaded file -> BGR array, width, height. Raises 400/413/415 with a clear message."""
    data = await read_upload(file, max_mb)
    return await run_in_threadpool(decode_image, data, file.filename)  # decoding a big JPEG is CPU work
