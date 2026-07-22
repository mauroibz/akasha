import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

MAX_COVER_BYTES = 10 * 1024 * 1024
MAX_COVER_PIXELS = 40_000_000
MAX_COVER_EDGE = 600


class CoverError(ValueError):
    pass


async def prepare_cover(client: httpx.AsyncClient, url: str, data_dir: Path) -> Path:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise CoverError("cover URL must use HTTPS")
    covers_dir = data_dir / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        async with client.stream("GET", url, follow_redirects=False) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";", 1)[0]
            if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise CoverError("cover response is not a supported image")
            declared = int(response.headers.get("content-length", "0"))
            if declared > MAX_COVER_BYTES:
                raise CoverError("cover exceeds byte limit")
            with tempfile.NamedTemporaryFile(
                dir=covers_dir, prefix="cover-", suffix=".tmp", delete=False
            ) as output:
                temporary = Path(output.name)
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_COVER_BYTES:
                        raise CoverError("cover exceeds byte limit")
                    output.write(chunk)
        assert temporary is not None
        with Image.open(temporary) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_COVER_PIXELS:
                raise CoverError("cover exceeds pixel limit")
            image.load()
            converted = image.convert("RGB")
            converted.thumbnail((MAX_COVER_EDGE, MAX_COVER_EDGE), Image.Resampling.LANCZOS)
            normalized = temporary.with_suffix(".jpg.tmp")
            converted.save(normalized, "JPEG", quality=85, optimize=True)
        temporary.unlink(missing_ok=True)
        return normalized
    except (
        CoverError,
        httpx.HTTPError,
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
            temporary.with_suffix(".jpg.tmp").unlink(missing_ok=True)
        if isinstance(error, CoverError):
            raise
        raise CoverError("cover could not be prepared") from error


def install_cover(prepared: Path, data_dir: Path, item_id: int) -> Path:
    target = data_dir / "covers" / f"{item_id}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(prepared, target)
    except OSError as error:
        prepared.unlink(missing_ok=True)
        raise CoverError("cover could not be installed") from error
    return target
