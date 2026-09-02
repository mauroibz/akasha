"""Anime's adapters: AniList for the record, Kitsu for the second opinion.

They sit in this domain's package rather than in `infrastructure/`, so the domain's
adapters, vocabulary and identity rule are one directory (technical spec 6.6).

Three things here are measured rather than assumed (DEC-088, 2026-08-27):

- **Both sources publish the MyAnimeList id**, AniList as `idMal` on the record and
  Kitsu as a `myanimelist/anime` mapping returned inside the *search* response. That is
  what makes anime the first domain since books whose candidates genuinely merge, so
  both adapters put it in `identifiers` on every row rather than only on a fetch.
- **AniList will not answer without a User-Agent.** Cloudflare returns `error code:
  1010` with HTTP 403. It is the first provider here for which the header is load-bearing
  rather than courteous.
- **A studio is not a person and never inverts.** Both sources are asked for the main
  studio and it is passed through as `creator_sort` unchanged, so the DEC-051 heuristic
  never runs on `MAPPA` — exactly what DEC-068 predicted for IGDB's companies.

Neither adapter leaks a raw provider response above infrastructure, and neither of them
fetches an image: they hand the shared pipeline a URL and it owns the rest.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

import httpx

from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json_object,
    parse_year,
)

ANILIST_ENDPOINT = "https://graphql.anilist.co"
KITSU_BASE = "https://kitsu.io/api/edge"
USER_AGENT = "Akasha/1.2 ({contact})"

# Kitsu spends its time before the first byte: TTFB measured 4.2, 5.0, 5.0 and 6.4
# seconds on 2026-09-02, against the shared client's 5-second read timeout. So a healthy
# Kitsu search was being cut by our own transport, retried, and the two attempts together
# overran the caller's budget — an empty anime search, with AniList's API disabled
# upstream and nothing else able to answer (DEC-125).
#
# Sized just under `search_providers`' own budget, because a second attempt cannot fit
# inside that budget anyway: one attempt as long as the caller will wait is strictly
# better than two that are each too short. `INTERACTIVE_ATTEMPTS` still earns its keep on
# a *fast* failure, where the retry does fit. One live search measured 7.98s end to end
# through the running container, so the headroom above the observed tail is deliberate.
KITSU_TIMEOUT_SECONDS = 9.0

# Observed `X-RateLimit-Limit: 30` on 2026-08-27, i.e. one request every two seconds
# averaged. AniList documents a higher ceiling and was serving a reduced one; pacing to
# what was actually measured is the conservative reading, and a search is one request,
# so nobody waits for this unless they are searching thirty times a minute.
ANILIST_MIN_INTERVAL_SECONDS = 2.0
# Kitsu published no rate-limit header across the whole measurement and answered every
# request, but its median was 3.7s with an 8.2s outlier, so it is paced gently rather
# than not at all.
KITSU_MIN_INTERVAL_SECONDS = 0.5

# What `MAX_COVER_EDGE` (600) wants. AniList's `extraLarge` measured 460x635 at 110 KiB;
# Kitsu's `large` is the right variant because its `original` is 980x1420 at 1.6 MiB.
KITSU_POSTER_VARIANT = "large"

#: The record, as both a search row and a fetched payload need it. One fragment so the
#: two queries cannot drift into returning different shapes.
_ANILIST_MEDIA_FIELDS = """
id idMal title { romaji english native } format episodes duration status
startDate { year } season seasonYear source countryOfOrigin siteUrl genres
studios(isMain: true) { nodes { name } }
coverImage { extraLarge }
description(asHtml: false)
"""


def _anilist_query(header: str, selection: str) -> str:
    """A GraphQL document around the shared field fragment.

    Concatenated rather than interpolated: GraphQL is made of braces, so an f-string or
    `str.format` would need every one of them doubled, and a query nobody can read is a
    query nobody will notice a mistake in.
    """
    return header + " { " + selection + " { " + _ANILIST_MEDIA_FIELDS + " } } }"


_ANILIST_SEARCH = _anilist_query(
    "query ($query: String, $perPage: Int) { Page(page: 1, perPage: $perPage)",
    "media(search: $query, type: ANIME, sort: SEARCH_MATCH)",
)
_ANILIST_BY_ID = (
    "query ($id: Int) { Media(id: $id, type: ANIME) { " + _ANILIST_MEDIA_FIELDS + " } }"
)
_ANILIST_BY_MAL = (
    "query ($idMal: Int) { Media(idMal: $idMal, type: ANIME) { " + _ANILIST_MEDIA_FIELDS + " } }"
)

#: How the recognizer says "this id is MyAnimeList's, not this provider's".
MAL_PREFIX = "mal:"

# AniList's enumerations, rendered for a person. Anything unlisted falls back to the
# raw value title-cased, so a value added upstream renders legibly instead of blank.
_ANILIST_FORMATS = {
    "TV": "TV",
    "TV_SHORT": "TV Short",
    "MOVIE": "Movie",
    "SPECIAL": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "MUSIC": "Music",
}
_ANILIST_AIRING = {
    "FINISHED": "Finished",
    "RELEASING": "Airing",
    "NOT_YET_RELEASED": "Not yet aired",
    "CANCELLED": "Cancelled",
    "HIATUS": "On hiatus",
}
# Kitsu spells the same two ideas in lower case and with different words.
_KITSU_SUBTYPES = {
    "TV": "TV",
    "movie": "Movie",
    "special": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "music": "Music",
}
_KITSU_AIRING = {
    "finished": "Finished",
    "current": "Airing",
    "tba": "To be announced",
    "unreleased": "Not yet aired",
    "upcoming": "Not yet aired",
}

_TAG = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n{3,}")


def _text(value: object) -> str | None:
    text = str(value).strip() if isinstance(value, str) else ""
    return text or None


def _whole(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _enumerated(value: object, table: Mapping[str, str]) -> str | None:
    """A provider enum as a person reads it, or a legible fallback for a new one."""
    raw = _text(value)
    if raw is None:
        return None
    return table.get(raw) or raw.replace("_", " ").title()


def _plain(value: object) -> str | None:
    """A synopsis with the markup taken out.

    AniList returns `<br>` inside `description` **even when asked for `asHtml: false`**,
    which is measured rather than defensive. The field is declared `long_text`, and no
    renderer here interprets markup, so a tag would be shown to the reader verbatim.
    """
    raw = _text(value)
    if raw is None:
        return None
    stripped = _TAG.sub("", raw).replace("&nbsp;", " ").replace("&amp;", "&")
    return _BLANK_LINES.sub("\n\n", stripped).strip() or None


def _names(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(name for name in (_text(value) for value in values) if name)


def _http_failure(label: str, error: httpx.HTTPStatusError) -> ProviderPayloadError:
    """A provider's HTTP status as a reason the layer above can act on.

    A raw `httpx` error above infrastructure is the same leak a raw provider row would
    be (technical spec 6.2), and the two codes are not interchangeable: a 404 is an
    answer — this record does not exist — while anything else is the provider being
    unwell, which is what the enrichment job's retry and the health notice read.

    AniList answers a record that does not exist with **404** and a GraphQL error body
    rather than a 200 carrying `null`, which is measured (DEC-088) and is why this
    translation exists at all.
    """
    status = error.response.status_code
    if status == 404:
        return ProviderPayloadError(f"{label} has no record for this id", code="record_not_found")
    return ProviderPayloadError(f"{label} returned HTTP {status}", code="provider_http_error")


class _Paced:
    """One request at a time, no faster than the source asked to be called."""

    def __init__(
        self,
        interval: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval = interval
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._last is not None:
                remaining = self._last + self._interval - now
                if remaining > 0:
                    await self._sleep(remaining)
            self._last = time.monotonic()


class AniListProvider:
    """AniList's GraphQL API. The primary source for this domain (DEC-088)."""

    name = "anilist"
    item_type = "anime"

    def __init__(
        self,
        client: httpx.AsyncClient,
        contact: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        min_interval_seconds: float = ANILIST_MIN_INTERVAL_SECONDS,
    ) -> None:
        self.client = client
        self.contact = contact
        self._paced = _Paced(min_interval_seconds, sleep)

    async def _query(self, query: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
        """One paced, retrying GraphQL request. Every call to AniList goes through here.

        It is a POST, which is why `bounded_json` grew a verb: writing a bespoke request
        loop here would have quietly dropped the retry policy and the byte bound.
        """
        await self._paced.wait()
        try:
            body = await bounded_json_object(
                self.client,
                ANILIST_ENDPOINT,
                params={},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    # Load-bearing: without it Cloudflare answers `error code: 1010`.
                    "User-Agent": USER_AGENT.format(contact=self.contact),
                },
                attempts=INTERACTIVE_ATTEMPTS,
                method="POST",
                json_body={"query": query, "variables": dict(variables)},
            )
        except httpx.HTTPStatusError as error:
            raise _http_failure("AniList", error) from error
        except httpx.HTTPError as error:
            raise ProviderPayloadError(
                "AniList could not be reached", code="provider_unreachable"
            ) from error
        data = body.get("data")
        if not isinstance(data, Mapping):
            raise ProviderPayloadError("AniList returned no data")
        return data

    def _candidate(self, media: Mapping[str, Any]) -> SearchCandidate | None:
        anilist_id = _whole(media.get("id"))
        titles = media.get("title")
        title_map: Mapping[str, Any] = titles if isinstance(titles, Mapping) else {}
        title = (
            _text(title_map.get("romaji"))
            or _text(title_map.get("english"))
            or _text(title_map.get("native"))
        )
        if anilist_id is None or title is None:
            return None
        studio_block = media.get("studios")
        nodes = studio_block.get("nodes") if isinstance(studio_block, Mapping) else []
        studios = _names(
            [node.get("name") for node in nodes or [] if isinstance(node, Mapping)],
        )
        start = media.get("startDate")
        year = parse_year((start or {}).get("year") if isinstance(start, Mapping) else None)
        season = _enumerated(media.get("season"), {})
        season_year = _whole(media.get("seasonYear"))
        cover = media.get("coverImage")
        # `idMal` is genuinely null for some legitimate records, and a candidate with no
        # shared identifier must merge with nothing rather than on a weaker key.
        mal_id = _whole(media.get("idMal"))
        metadata: dict[str, Any] = {
            "creators": list(studios),
            "english_title": _text(title_map.get("english")),
            "japanese_title": _text(title_map.get("native")),
            "kind": _enumerated(media.get("format"), _ANILIST_FORMATS),
            "episodes": _whole(media.get("episodes")),
            "episode_minutes": _whole(media.get("duration")),
            "season": f"{season} {season_year}" if season and season_year else season,
            "source": _enumerated(media.get("source"), {}),
            "genres": _names(media.get("genres") or []) or None,
            "airing_status": _enumerated(media.get("status"), _ANILIST_AIRING),
            "synopsis": _plain(media.get("description")),
        }
        return SearchCandidate(
            source=self.name,
            source_id=str(anilist_id),
            source_refs=(SourceRef(self.name, str(anilist_id)),),
            title=title,
            subtitle=None,
            creators=studios,
            year=year or (season_year if season_year else None),
            cover_url=_text(cover.get("extraLarge")) if isinstance(cover, Mapping) else None,
            identifiers={"mal": str(mal_id)} if mal_id is not None else {},
            language=None,
            metadata={key: value for key, value in metadata.items() if value not in (None, [], "")},
            creator_sort=studios[0] if studios else None,
        )

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        data = await self._query(_ANILIST_SEARCH, {"query": query, "perPage": limit})
        page = data.get("Page")
        media = page.get("media") if isinstance(page, Mapping) else None
        if not isinstance(media, list):
            raise ProviderPayloadError("AniList returned no media")
        rows = [self._candidate(row) for row in media if isinstance(row, Mapping)]
        return [row for row in rows if row is not None][:limit]

    async def fetch(self, source_id: str) -> ItemPayload:
        """Fetch by AniList id, or by MyAnimeList id when the value is `mal:`-prefixed.

        The prefix is how `recognize_anime_url` hands over a `myanimelist.net` link:
        MyAnimeList's own mirror is not registered (DEC-088) and AniList resolves the id
        directly, so a reader's MAL bookmark still works without one.
        """
        value = source_id.strip()
        if value.startswith(MAL_PREFIX):
            raw = value[len(MAL_PREFIX) :]
            if not raw.isdigit():
                raise ProviderPayloadError(f"{source_id!r} is not a MyAnimeList id")
            data = await self._query(_ANILIST_BY_MAL, {"idMal": int(raw)})
        else:
            if not value.isdigit():
                raise ProviderPayloadError(f"{source_id!r} is not an AniList id")
            data = await self._query(_ANILIST_BY_ID, {"id": int(value)})
        media = data.get("Media")
        if not isinstance(media, Mapping):
            raise ProviderPayloadError("AniList returned no record for this id")
        candidate = self._candidate(media)
        if candidate is None:
            raise ProviderPayloadError("AniList returned a record with no usable title")
        return ItemPayload(**vars(candidate))

    async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
        """Background enrichment's entry point (DEC-067 row 3).

        Anime's declared key is `mal`, and AniList resolves it directly through
        `Media(idMal:)` — no mapping hop, which is one reason it is the primary.
        """
        if kind != "mal":
            raise ProviderPayloadError(
                f"AniList cannot look a record up by {kind!r}",
                code="unsupported_identity_kind",
            )
        return await self.fetch(f"{MAL_PREFIX}{value}")


class KitsuProvider:
    """Kitsu's JSON:API. The second source, and the hedge behind AniList (DEC-088)."""

    name = "kitsu"
    item_type = "anime"
    #: Everything one fetch needs. Studios and genres are `include`s rather than extra
    #: requests, which is what makes a second provider affordable at all.
    FETCH_INCLUDE = "animeProductions.producer,categories,mappings"

    def __init__(
        self,
        client: httpx.AsyncClient,
        contact: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        min_interval_seconds: float = KITSU_MIN_INTERVAL_SECONDS,
    ) -> None:
        self.client = client
        self.contact = contact
        self._paced = _Paced(min_interval_seconds, sleep)

    async def _json(self, path: str, params: Mapping[str, str | int]) -> Mapping[str, Any]:
        await self._paced.wait()
        try:
            return await bounded_json_object(
                self.client,
                f"{KITSU_BASE}{path}",
                params=params,
                headers={
                    "Accept": "application/vnd.api+json",
                    "User-Agent": USER_AGENT.format(contact=self.contact),
                },
                timeout=KITSU_TIMEOUT_SECONDS,
                attempts=INTERACTIVE_ATTEMPTS,
            )
        except httpx.HTTPStatusError as error:
            raise _http_failure("Kitsu", error) from error
        except httpx.HTTPError as error:
            raise ProviderPayloadError(
                "Kitsu could not be reached", code="provider_unreachable"
            ) from error

    @staticmethod
    def _included(body: Mapping[str, Any]) -> dict[str, dict[str, Mapping[str, Any]]]:
        """JSON:API side-loaded resources, indexed by type and id."""
        grouped: dict[str, dict[str, Mapping[str, Any]]] = {}
        for row in body.get("included") or []:
            if isinstance(row, Mapping) and row.get("type") and row.get("id"):
                grouped.setdefault(str(row["type"]), {})[str(row["id"])] = row
        return grouped

    @staticmethod
    def _related(resource: Mapping[str, Any], name: str) -> list[str]:
        relationships = resource.get("relationships")
        if not isinstance(relationships, Mapping):
            return []
        entry = relationships.get(name)
        data = entry.get("data") if isinstance(entry, Mapping) else None
        if isinstance(data, Mapping):
            data = [data]
        return [str(row["id"]) for row in data or [] if isinstance(row, Mapping) and row.get("id")]

    def _mal_id(
        self, resource: Mapping[str, Any], included: Mapping[str, dict[str, Mapping[str, Any]]]
    ) -> str | None:
        """The MyAnimeList mapping, which arrives on a *search* row and not only a fetch.

        Eight mappings come back for one series — AniDB, TheTVDB, Trakt, Hulu and others
        among them — so the site has to be matched rather than the first one taken.
        """
        mappings = included.get("mappings", {})
        for mapping_id in self._related(resource, "mappings"):
            attributes = mappings.get(mapping_id, {}).get("attributes")
            if not isinstance(attributes, Mapping):
                continue
            if attributes.get("externalSite") == "myanimelist/anime":
                value = _text(attributes.get("externalId"))
                if value and value.isdigit():
                    return value
        return None

    def _studios(
        self, resource: Mapping[str, Any], included: Mapping[str, dict[str, Mapping[str, Any]]]
    ) -> tuple[str, ...]:
        """The animation studio, not the first company attached to the production.

        Akame ga Kill! returns four producers: Square Enix and TOHO animation as
        `producer`, Sentai Filmworks as `licensor`, and White Fox as `studio`. Taking
        the first would have filed the series under its manga publisher.
        """
        productions = included.get("animeProductions", {})
        producers = included.get("producers", {})
        names: list[str] = []
        for production_id in self._related(resource, "animeProductions"):
            production = productions.get(production_id)
            if not isinstance(production, Mapping):
                continue
            attributes = production.get("attributes")
            if not isinstance(attributes, Mapping) or attributes.get("role") != "studio":
                continue
            for producer_id in self._related(production, "producer"):
                producer = producers.get(producer_id, {}).get("attributes")
                name = _text(producer.get("name")) if isinstance(producer, Mapping) else None
                if name and name not in names:
                    names.append(name)
        return tuple(names)

    def _genres(
        self, resource: Mapping[str, Any], included: Mapping[str, dict[str, Mapping[str, Any]]]
    ) -> tuple[str, ...]:
        categories = included.get("categories", {})
        return _names(
            [
                categories.get(category_id, {}).get("attributes", {}).get("title")
                for category_id in self._related(resource, "categories")
            ]
        )

    def _candidate(
        self, resource: Mapping[str, Any], included: Mapping[str, dict[str, Mapping[str, Any]]]
    ) -> SearchCandidate | None:
        kitsu_id = _text(resource.get("id"))
        attributes = resource.get("attributes")
        if kitsu_id is None or not isinstance(attributes, Mapping):
            return None
        titles = attributes.get("titles")
        title_map: Mapping[str, Any] = titles if isinstance(titles, Mapping) else {}
        title = _text(attributes.get("canonicalTitle")) or _text(title_map.get("en_jp"))
        if title is None:
            return None
        studios = self._studios(resource, included)
        poster = attributes.get("posterImage")
        mal_id = self._mal_id(resource, included)
        genres = self._genres(resource, included)
        metadata: dict[str, Any] = {
            "creators": list(studios),
            "english_title": _text(title_map.get("en")),
            "japanese_title": _text(title_map.get("ja_jp")),
            "kind": _enumerated(attributes.get("subtype"), _KITSU_SUBTYPES),
            "episodes": _whole(attributes.get("episodeCount")),
            "episode_minutes": _whole(attributes.get("episodeLength")),
            "genres": list(genres) or None,
            "airing_status": _enumerated(attributes.get("status"), _KITSU_AIRING),
            "synopsis": _plain(attributes.get("synopsis") or attributes.get("description")),
        }
        return SearchCandidate(
            source=self.name,
            source_id=kitsu_id,
            source_refs=(SourceRef(self.name, kitsu_id),),
            title=title,
            subtitle=None,
            creators=studios,
            year=parse_year(attributes.get("startDate")),
            cover_url=(
                _text(poster.get(KITSU_POSTER_VARIANT)) if isinstance(poster, Mapping) else None
            ),
            identifiers={"mal": mal_id} if mal_id else {},
            language=None,
            metadata={key: value for key, value in metadata.items() if value not in (None, [], "")},
            creator_sort=studios[0] if studios else None,
        )

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        body = await self._json(
            "/anime",
            # `include=mappings` is not decoration: without it a Kitsu row carries no
            # MyAnimeList id and could never merge with an AniList one.
            {"filter[text]": query, "page[limit]": limit, "include": "mappings"},
        )
        rows = body.get("data")
        if not isinstance(rows, list):
            raise ProviderPayloadError("Kitsu returned no anime")
        included = self._included(body)
        candidates = [self._candidate(row, included) for row in rows if isinstance(row, Mapping)]
        return [row for row in candidates if row is not None][:limit]

    async def fetch(self, source_id: str) -> ItemPayload:
        """Fetch by numeric id, or by slug when a reader pasted one."""
        value = source_id.strip()
        if value.isdigit():
            body = await self._json(f"/anime/{value}", {"include": self.FETCH_INCLUDE})
            resource = body.get("data")
        else:
            body = await self._json(
                "/anime", {"filter[slug]": value, "include": self.FETCH_INCLUDE}
            )
            rows = body.get("data")
            resource = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(resource, Mapping):
            raise ProviderPayloadError("Kitsu returned no record for this id")
        candidate = self._candidate(resource, self._included(body))
        if candidate is None:
            raise ProviderPayloadError("Kitsu returned a record with no usable title")
        return ItemPayload(**vars(candidate))

    async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
        """Background enrichment's entry point, in two requests.

        Kitsu keys its own records by its own id, so a MyAnimeList id is resolved
        through `mappings` first. Nested includes are refused with a 400 (measured
        2026-08-27), so the mapping response cannot carry the studios and genres the
        record needs — and two of anime's three completeness fields are exactly those,
        so a one-request answer would leave every record looking incomplete for ever.
        Kitsu is the fallback provider, so the second request is only ever paid once
        AniList has already failed.
        """
        if kind != "mal":
            raise ProviderPayloadError(
                f"Kitsu cannot look a record up by {kind!r}",
                code="unsupported_identity_kind",
            )
        body = await self._json(
            "/mappings",
            {
                "filter[externalSite]": "myanimelist/anime",
                "filter[externalId]": value,
                # Without this the relationship carries links and no id, so the record
                # could not be reached at all.
                "include": "item",
            },
        )
        rows = body.get("data")
        mapping = rows[0] if isinstance(rows, list) and rows else None
        related = self._related(mapping, "item") if isinstance(mapping, Mapping) else []
        if not related:
            raise ProviderPayloadError(
                f"Kitsu has no record mapped to MyAnimeList id {value}",
                code="record_not_found",
            )
        return await self.fetch(related[0])
