import os
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from PIL import Image, UnidentifiedImageError

MAX_COVER_BYTES = 10 * 1024 * 1024
MAX_COVER_PIXELS = 40_000_000
MAX_COVER_EDGE = 600
MAX_COVER_REDIRECTS = 3
# Providers answer "image not available" with a wide, short banner rather than a 404.
# Google Books' is 575x92 — 6.25:1 — where real covers measured 0.66:1 and 0.77:1
# (DEC-044). The threshold sits far from both: no book cover is three times as wide as
# it is tall, and Open Library needs no guard at all because its URLs carry
# `?default=false` and answer 404 instead.
MAX_COVER_ASPECT_RATIO = 3.0
# The detail page paints a cover about 240px wide, so anything much under this is
# visibly broken rather than merely small. Open Library serves whatever scan it holds
# behind a `-L.jpg` URL and for some cover ids that is a 60x40 thumbnail, which Sprint
# 020's walkthrough duly installed. Applies to provider downloads only; what someone
# deliberately uploads is their business.
MIN_PROVIDER_COVER_EDGE = 200
ALLOWED_COVER_HOSTS = {
    "covers.openlibrary.org",
    "books.google.com",
    "books.googleusercontent.com",
    "archive.org",
    "coverartarchive.org",
    # Anime art (DEC-088). Both measured 2026-08-27 against the bounds above: AniList's
    # `coverImage.extraLarge` is 460x635 at 110 KiB, and Kitsu's `posterImage.large` is
    # the variant to ask for — its `original` is 980x1420 at 1.6 MiB. The list stays
    # central so a domain cannot widen it from its own package (DEC-067 row 4).
    "s4.anilist.co",
    "media.kitsu.app",
}
# The Cover Art Archive redirects through `archive.org` to a numbered storage node —
# `dn710907.ca.archive.org` was the one observed — which no fixed list can enumerate.
# The rule is a subdomain of archive.org, so `notarchive.org` and
# `archive.org.evil.example` are still refused; it subsumes the older `.us.archive.org`.
ALLOWED_COVER_HOST_SUFFIX = ".archive.org"


class CoverError(ValueError):
    pass


def prepare_uploaded_cover(content: bytes, content_type: str, data_dir: Path) -> Path:
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise CoverError("cover upload is not a supported image")
    if len(content) > MAX_COVER_BYTES:
        raise CoverError("cover exceeds byte limit")
    covers_dir = data_dir / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=covers_dir, prefix="upload-", suffix=".tmp", delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(content)
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
    except (CoverError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
            temporary.with_suffix(".jpg.tmp").unlink(missing_ok=True)
        if isinstance(error, CoverError):
            raise
        raise CoverError("cover could not be prepared") from error


def _no_placeholder(url: str) -> str:
    """Ask Open Library for a 404 rather than its "No image available" substitute.

    The geometry guard above catches Google Books' placeholder because it is a 6.25:1
    banner. Open Library's is a portrait image of ordinary size, so no shape or byte
    heuristic tells it apart from a real cover — Sprint 020's walkthrough installed one
    at 325x500 and it passed every check. `default=false` is the only reliable answer,
    and it is applied here rather than trusted to whatever URL arrived, because the
    cover chooser accepts a URL from the client.
    """
    parts = urlsplit(url)
    if (parts.hostname or "") != "covers.openlibrary.org":
        return url
    query = [(key, value) for key, value in parse_qsl(parts.query) if key != "default"]
    query.append(("default", "false"))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


async def prepare_cover(client: httpx.AsyncClient, url: str, data_dir: Path) -> Path:
    def as_https(value: str) -> str:
        """Rewrite `http://` to https before anything looks at it.

        The Cover Art Archive answers `http://` in its JSON *and* in both redirect
        hops (DEC-052 seam 4). Loosening the scheme check would have accepted a
        plaintext fetch; upgrading first means nothing is ever fetched over http and
        an allowlisted host is not lost to a provider's habit.
        """
        parsed = urlsplit(value)
        if parsed.scheme != "http":
            return value
        return urlunsplit(("https", *parsed[1:]))

    def validate_url(value: str) -> None:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        allowed = host in ALLOWED_COVER_HOSTS or host.endswith(ALLOWED_COVER_HOST_SUFFIX)
        if parsed.scheme != "https" or not allowed:
            raise CoverError("cover URL must use an allowlisted HTTPS host")

    url = as_https(url)
    validate_url(url)
    url = _no_placeholder(url)
    covers_dir = data_dir / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        current = url
        response: httpx.Response | None = None
        for redirect_count in range(MAX_COVER_REDIRECTS + 1):
            response = await client.send(client.build_request("GET", current), stream=True)
            if response.status_code not in {301, 302, 303, 307, 308}:
                break
            if redirect_count == MAX_COVER_REDIRECTS:
                raise CoverError("cover exceeded redirect limit")
            location = response.headers.get("location")
            if not location:
                await response.aclose()
                raise CoverError("cover redirect has no location")
            await response.aclose()
            current = as_https(urljoin(current, location))
            validate_url(current)
        assert response is not None
        try:
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
        finally:
            await response.aclose()
        assert temporary is not None
        with Image.open(temporary) as image:
            width, height = image.size
            if width < 10 or height < 10 or width * height > MAX_COVER_PIXELS:
                raise CoverError("cover exceeds pixel limit")
            if width > height * MAX_COVER_ASPECT_RATIO:
                raise CoverError("cover looks like a provider placeholder banner")
            if width < MIN_PROVIDER_COVER_EDGE or height < MIN_PROVIDER_COVER_EDGE:
                raise CoverError("cover image is too small to use")
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
