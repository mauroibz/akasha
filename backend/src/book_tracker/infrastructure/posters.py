"""The keyless poster URL builder, shared by every domain keyed on an IMDb id.

Stremio's image service is deterministic from the IMDb id, keyless, and answered
14 of 14 films and 15 of 16 series measured live (DEC-103, DEC-104). It lives in
infrastructure rather than in any domain's package because two domains need it and
a domain package may not import another (technical spec 6.6). It builds a URL; it
performs no request, which is what makes it shared infrastructure rather than a
provider detail.
"""

from __future__ import annotations

import re

#: Stremio's image service. Keyed on IMDb id, keyless, and deterministic — which is the
#: whole reason it is primary: a poster for every title costs zero requests.
METAHUB_POSTER = "https://images.metahub.space/poster/medium/{imdb_id}/img"

_IMDB_ID = re.compile(r"tt[0-9]{7,10}")


def metahub_poster_url(imdb_id: str | None) -> str | None:
    """The Stremio poster URL for an IMDb id, or `None` if there is no usable id.

    Built rather than fetched. There is no request here and no failure mode: if the
    title has no poster the URL 404s when the cover pipeline tries it, and a title that
    fails to get a cover is exactly as it was before.
    """
    value = (imdb_id or "").strip()
    return METAHUB_POSTER.format(imdb_id=value) if _IMDB_ID.fullmatch(value) else None
