import io

import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError


async def load_upload(file: UploadFile, max_mb: int) -> tuple[np.ndarray, int, int]:
    """Uploaded file -> BGR array (EXIF rotation applied), width, height."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"Пустой файл: {file.filename}")
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Файл больше {max_mb} МБ: {file.filename}")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")  # respect phone photo rotation
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=415, detail=f"Не изображение (PNG, JPG, WEBP, BMP, TIFF): {file.filename}"
        ) from None
    rgb = np.asarray(img)
    return rgb[:, :, ::-1].copy(), img.width, img.height
