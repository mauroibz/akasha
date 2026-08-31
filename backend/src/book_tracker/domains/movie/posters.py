"""Where a film's poster comes from.

Wikidata has no posters and structurally cannot: posters are copyrighted, Wikimedia
Commons hosts free media, and Wikidata's own `P3383` film-poster property was present on
one of eight sampled films — a 1927 lithograph that is public domain by age. That is why
Sprint 046 shipped movies coverless (DEC-098), and why the answer had to come from
somewhere else.

Measured live on 2026-08-28 before this was written:

- **Stremio's image service answered 14 of 14 films**, chosen to be hard: Argentine
  cinema including `La flor` and `Pizza birra faso`, `Sátántangó`, `Tokyo Story`, `Cure`
  and Apichatpong's first feature. No key, no account, no setup.
- **Its URL is deterministic from the IMDb id**, so a poster costs **no request at all**.
  TMDB needs one lookup per film to learn its opaque `poster_path`.
- **A miss is a clean 404**, not a placeholder, so nothing junk is ever installed.
- **`medium` is 500x750**, which clears `MIN_PROVIDER_COVER_EDGE` and downscales to
  `MAX_COVER_EDGE` without upscaling. Both JPEG and WebP come back, and the cover
  pipeline already accepts each.
- **49 of 50 sampled films carrying a TMDB id also carry an IMDb id.** The remaining ~2%
  are the only case Stremio cannot serve, and the only case worth spending a key on.

Neither source is asked for anything but a URL. Everything after that — https, the host
allowlist, redirects, byte, pixel and aspect bounds, the downscale — belongs to
`infrastructure/covers.py` and is not duplicated here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import httpx

from book_tracker.infrastructure.posters import METAHUB_POSTER, metahub_poster_url
from book_tracker.infrastructure.providers import INTERACTIVE_ATTEMPTS, bounded_json_object

__all__ = ["METAHUB_POSTER", "TmdbPosters", "metahub_poster_url", "poster_for"]
#: `medium` measured 500x750. `small` is 300x450 and would upscale to the 600 the cover
#: pipeline targets; `large` is 780x1170 and is bytes nobody sees. Same reasoning the
#: anime adapter used to pick Kitsu's `large` over its `original`.
TMDB_API = "https://api.themoviedb.org/3"
#: TMDB's own published image base. `w500` is 500 wide for the same reason as above.
TMDB_IMAGE = "https://image.tmdb.org/t/p/w500{poster_path}"

_TMDB_ID = re.compile(r"[0-9]{1,12}")


class TmdbPosters:
    """The narrow fallback: films that carry a TMDB id and no IMDb id.

    Deliberately not the primary source. It needs a key, and it costs one request per
    film to learn a `poster_path` that cannot be constructed — against a keyless source
    that answered every film measured and costs nothing. It earns its place on the ~2%
    Stremio cannot address at all.
    """

    def __init__(self, client: httpx.AsyncClient, read_token: str) -> None:
        self.client = client
        self.read_token = read_token

    @property
    def enabled(self) -> bool:
        return bool(self.read_token)

    async def poster_url(self, tmdb_id: str | None) -> str | None:
        """One lookup, or `None` for anything this cannot answer.

        Never raises. A poster is a nicety on top of a record that is already complete,
        so a provider having a bad day must not fail the search or the job it is part of.
        """
        value = (tmdb_id or "").strip()
        if not self.enabled or not _TMDB_ID.fullmatch(value):
            return None
        try:
            body = await bounded_json_object(
                self.client,
                f"{TMDB_API}/movie/{value}",
                params={},
                headers={
                    "Authorization": f"Bearer {self.read_token}",
                    "Accept": "application/json",
                },
                attempts=INTERACTIVE_ATTEMPTS,
            )
        except Exception:
            return None
        path = body.get("poster_path")
        return TMDB_IMAGE.format(poster_path=path) if isinstance(path, str) and path else None


async def poster_for(identifiers: Mapping[str, str], tmdb: TmdbPosters | None = None) -> str | None:
    """The poster URL for a film, from whichever source can answer without waste.

    Stremio first, because it is keyless and free. TMDB is consulted **only** when there
    is no IMDb id at all — with both present, asking TMDB would spend a request to
    duplicate an answer already in hand.
    """
    stremio = metahub_poster_url(identifiers.get("imdb"))
    if stremio is not None:
        return stremio
    if tmdb is not None:
        return await tmdb.poster_url(identifiers.get("tmdb"))
    return None
