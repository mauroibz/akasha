"""Movies' adapter: Wikidata's official Action API, and nothing else.

It sits in this domain's package rather than in `infrastructure/`, so the domain's
adapter, vocabulary and identity rule are one directory (technical spec 6.6).

Five things here are measured rather than assumed (DEC-098, 2026-08-27):

- **A film-filtered search is load-bearing.** `haswbstatement:P31=Q11424` is what keeps
  a record label, a novel and three video games out of a search for `Metropolis`; the
  unfiltered control put the 1927 film tenth.
- **A search cannot be one request.** `wbgetentities` with claims costs ~113 KB for one
  film and **1.9 MB for ten**, against `MAX_PROVIDER_BYTES` of 2 MiB. Entities are read
  in small batches and the candidate count is bounded, so no single read approaches the
  limit and no search spends more than a handful of requests.
- **Claims have ranks, and the first one is regularly wrong.** `Q546900` lists German,
  Latin, *preferred* Italian and English as original languages, in that order; `Q151599`
  opens with a **deprecated** country and a `P364` with no value at all. Every claim is
  read through `_best`, which drops deprecated statements and prefers preferred ones.
- **`maxlag` is answered with HTTP 200.** A lagging replica returns an `error` object in
  an otherwise ordinary body, so nothing below this notices it. It is translated here.
- **There is no poster.** Four of five measured films had no `P18`; the one that did had
  a set photograph. This adapter never emits a cover URL, and does not read `P18`.

Nothing raw leaves this module: not a provider row, and not an `httpx` exception.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import httpx

from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.domains.movie.posters import TmdbPosters, poster_for
from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json_object,
)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "Akasha/1.3 ({contact})"

#: Instance-of film. The whole difference between a movie search and a word search.
FILM_FILTER = "haswbstatement:P31=Q11424"

# Wikimedia asks clients to use `maxlag` so a replica that has fallen behind sheds load
# rather than serving stale reads. Five seconds is the value their own guidance suggests
# for interactive clients.
MAXLAG_SECONDS = 5
# Measured 2026-08-27: 1 entity ~113 KB, 5 entities up to 1.15 MB, 10 entities 1.9 MB.
# `MAX_PROVIDER_BYTES` is 2 MiB, so three at a time leaves real headroom for a film with
# an unusually long claim list.
ENTITY_BATCH_SIZE = 3
# Six bounded entity reads is already four requests for one search. The film filter
# means the answer is at the top of a short list rather than buried in a long one.
MAX_SEARCH_RESULTS = 6
#: `wbgetentities` accepts 50 ids per anonymous request; labels are small.
LABEL_BATCH_SIZE = 50
#: A detail page is not a call sheet. `Q748851` credits thirty-one people.
MAX_CAST = 12
# Wikidata publishes no rate-limit header for anonymous reads and asks only that clients
# be considerate. A search is four requests, so a fifth of a second between them keeps a
# search under a second of self-imposed delay while never bursting.
MIN_INTERVAL_SECONDS = 0.2
#: `boxd.it` resolved in exactly one hop when measured; three is room for a change of
#: infrastructure, not for a chain.
MAX_SHORT_URI_REDIRECTS = 3

# The claims a film is read from. Everything else on the entity is ignored, including
# `P18`: it is a general image property and the one measured value was a set photograph.
P_INSTANCE_OF = "P31"
P_DIRECTOR = "P57"
P_COUNTRY = "P495"
P_ORIGINAL_LANGUAGE = "P364"
P_GENRE = "P136"
P_DURATION = "P2047"
P_CAST = "P161"
P_PUBLICATION_DATE = "P577"
P_ORIGINAL_TITLE = "P1476"
P_IMDB = "P345"
P_TMDB_MOVIE = "P4947"
P_LETTERBOXD = "P6127"

Q_FILM = "Q11424"
_UNIT_MINUTE = "Q7727"
_UNIT_SECOND = "Q11574"

#: Which stored identifier kind comes from which claim, and what a valid value looks
#: like. The pattern is what stops a typo in a paste from becoming an exact lookup.
IDENTITY_CLAIMS: Mapping[str, tuple[str, re.Pattern[str]]] = {
    "imdb": (P_IMDB, re.compile(r"tt[0-9]{7,10}")),
    "tmdb": (P_TMDB_MOVIE, re.compile(r"[0-9]{1,12}")),
    "letterboxd": (P_LETTERBOXD, re.compile(r"[a-z0-9][a-z0-9-]{0,120}")),
}

_Q_ID = re.compile(r"Q[1-9][0-9]*")
_YEAR = re.compile(r"^[+-]?(\d{4})")
_LETTERBOXD_FILM_PATH = re.compile(r"/film/([a-z0-9][a-z0-9-]*)/?")
_LETTERBOXD_HOSTS = {"letterboxd.com", "www.letterboxd.com"}
_SHORT_URI_HOSTS = {"boxd.it"}

#: Spanish first, English as the fallback. Both were present on every measured entity
#: and on all forty-one of their linked values, so this is a preference rather than a
#: hope (DEC-098).
LANGUAGES = ("es", "en")


def wikidata_route_key(request: httpx.Request) -> str:
    """Which operation a request is, for a source that answers them all at one path.

    Search, entity reads and label reads are all `GET /w/api.php`, so a path does not
    identify a response. This names the three by what actually distinguishes them, and
    the test transport replays recordings by the same name.
    """
    params = dict(parse_qsl(request.url.query.decode()))
    action = params.get("action")
    if action == "query":
        return f"search:{params.get('srsearch', '')}"
    if action == "wbgetentities":
        props = params.get("props", "")
        prefix = "labels" if props == "labels" else f"entities:{props}"
        return f"{prefix}:{params.get('ids', '')}"
    return request.url.path


# --------------------------------------------------------------------------------------
# Reading one claim
# --------------------------------------------------------------------------------------


def _statements(claims: Mapping[str, Any], prop: str) -> list[Mapping[str, Any]]:
    rows = claims.get(prop)
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _best(statements: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The statements Wikidata considers true, preferring the ones it prefers.

    Rank is not decoration. A `deprecated` statement is one the community has explicitly
    marked wrong — Metropolis' country of origin is recorded that way — and a `preferred`
    one is the answer among several that are all defensible. Reading the first element of
    the list gets both of those backwards.
    """
    live = [row for row in statements if row.get("rank") != "deprecated"]
    return [row for row in live if row.get("rank") == "preferred"] or live


def _value(statement: Mapping[str, Any]) -> Any | None:
    """The snak's value, or `None` for `somevalue` and `novalue`.

    `Q151599` opens with an original language that is `somevalue`: Wikidata is saying it
    knows one exists and not which. Rendering that as a fact would invent one.
    """
    snak = statement.get("mainsnak")
    if not isinstance(snak, Mapping) or snak.get("snaktype") != "value":
        return None
    datavalue = snak.get("datavalue")
    return datavalue.get("value") if isinstance(datavalue, Mapping) else None


def _entity_ids(claims: Mapping[str, Any], prop: str, *, limit: int | None = None) -> list[str]:
    """The linked `Q` ids of a claim, best-ranked, in the order the entity lists them."""
    found: list[str] = []
    for statement in _best(_statements(claims, prop)):
        value = _value(statement)
        if isinstance(value, Mapping) and isinstance(value.get("id"), str):
            found.append(value["id"])
    return found[:limit] if limit is not None else found


def _external_id(claims: Mapping[str, Any], prop: str, pattern: re.Pattern[str]) -> str | None:
    """One external identifier, only if it looks like one.

    Wikidata is edited by people, and a value that does not match its own property's
    shape is a typo rather than an identity. Storing it would make the next lookup on
    that kind resolve to somebody else's film.
    """
    for statement in _best(_statements(claims, prop)):
        value = _value(statement)
        if isinstance(value, str) and pattern.fullmatch(value.strip()):
            return value.strip()
    return None


def _year(claims: Mapping[str, Any]) -> int | None:
    """The earliest best-ranked release year.

    A film has one date per country — `Q151599` carries thirty — so the release year is
    the earliest of them, not the first one listed. Precision below `9` is a decade or
    coarser and says nothing about a year. The date is read as text on purpose:
    `+1977-03-00T00:00:00Z` is a real, valid, month-precision Wikidata timestamp and no
    date parser will accept day zero.
    """
    years: list[int] = []
    for statement in _best(_statements(claims, P_PUBLICATION_DATE)):
        value = _value(statement)
        if not isinstance(value, Mapping) or not isinstance(value.get("time"), str):
            continue
        precision = value.get("precision")
        if not isinstance(precision, int) or precision < 9:
            continue
        match = _YEAR.match(value["time"])
        if match:
            years.append(int(match.group(1)))
    return min(years) if years else None


def _minutes(claims: Mapping[str, Any]) -> int | None:
    """A runtime, read with its unit rather than as a bare number.

    Every measured film used minutes, but the same property legitimately carries seconds,
    and a quantity whose unit says neither is not a runtime this can render.
    """
    for statement in _best(_statements(claims, P_DURATION)):
        value = _value(statement)
        if not isinstance(value, Mapping):
            continue
        amount = str(value.get("amount") or "").lstrip("+")
        unit = str(value.get("unit") or "").rsplit("/", 1)[-1]
        try:
            number = float(amount)
        except ValueError:
            continue
        if number <= 0:
            continue
        if unit == _UNIT_MINUTE:
            return int(number)
        if unit == _UNIT_SECOND:
            return int(number // 60) or None
    return None


def _monolingual(claims: Mapping[str, Any], prop: str) -> str | None:
    for statement in _best(_statements(claims, prop)):
        value = _value(statement)
        if isinstance(value, Mapping):
            text = value.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _localized(block: Any) -> str | None:
    """A label or description in the reader's language, falling back to English."""
    if not isinstance(block, Mapping):
        return None
    for language in LANGUAGES:
        entry = block.get(language)
        if isinstance(entry, Mapping):
            text = entry.get("value")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _is_film(claims: Mapping[str, Any]) -> bool:
    return Q_FILM in _entity_ids(claims, P_INSTANCE_OF)


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


def _http_failure(error: httpx.HTTPStatusError) -> ProviderPayloadError:
    """A provider's HTTP status as a reason the layer above can act on.

    A 404 is an answer — this record does not exist — while anything else is the provider
    being unwell, which is what the enrichment job's retry and the health notice read.
    """
    status = error.response.status_code
    if status == 404:
        return ProviderPayloadError(
            "Wikidata has no record at this address", code="record_not_found"
        )
    return ProviderPayloadError(f"Wikidata returned HTTP {status}", code="provider_http_error")


class WikidataMovieProvider:
    """The movie domain's one adapter (DEC-098). Keyless, CC0, and deliberately modest."""

    name = "wikidata"
    item_type = "movie"

    def __init__(
        self,
        client: httpx.AsyncClient,
        contact: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        min_interval_seconds: float = MIN_INTERVAL_SECONDS,
        entity_batch_size: int = ENTITY_BATCH_SIZE,
        posters: TmdbPosters | None = None,
    ) -> None:
        self.client = client
        self.contact = contact
        self.entity_batch_size = max(1, entity_batch_size)
        # Wikidata has no posters and cannot have them (DEC-098). Sprint 048 supplies
        # them from the identifiers this adapter already extracts, without asking
        # Wikidata for anything more.
        self.posters = posters
        self._paced = _Paced(min_interval_seconds, sleep)

    # -- the boundary ---------------------------------------------------------------

    async def _read(self, params: Mapping[str, str | int]) -> Mapping[str, Any]:
        """One paced, retrying, bounded read. Every call to Wikidata goes through here."""
        await self._paced.wait()
        try:
            body = await bounded_json_object(
                self.client,
                WIKIDATA_API,
                params={
                    **params,
                    "format": "json",
                    "formatversion": 2,
                    "maxlag": MAXLAG_SECONDS,
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT.format(contact=self.contact),
                },
                attempts=INTERACTIVE_ATTEMPTS,
            )
        except httpx.HTTPStatusError as error:
            raise _http_failure(error) from error
        except httpx.HTTPError as error:
            raise ProviderPayloadError(
                "Wikidata could not be reached", code="provider_unreachable"
            ) from error
        error_block = body.get("error")
        if isinstance(error_block, Mapping):
            # A lagging replica answers 200 with this rather than a status the retry
            # policy would recognize, so it is translated into an outage here.
            code = str(error_block.get("code") or "unknown")
            raise ProviderPayloadError(
                f"Wikidata declined the request ({code})", code="provider_http_error"
            )
        return body

    async def _search_ids(self, srsearch: str, limit: int) -> list[str]:
        body = await self._read(
            {"action": "query", "list": "search", "srsearch": srsearch, "srlimit": limit}
        )
        query = body.get("query")
        rows = query.get("search") if isinstance(query, Mapping) else None
        if not isinstance(rows, list):
            raise ProviderPayloadError("Wikidata returned no search results block")
        found: list[str] = []
        for row in rows:
            title = row.get("title") if isinstance(row, Mapping) else None
            if isinstance(title, str) and _Q_ID.fullmatch(title):
                found.append(title)
        return found

    async def _entities(self, ids: Sequence[str], props: str) -> dict[str, Mapping[str, Any]]:
        """Entities for a bounded batch of ids, in the order they were asked for."""
        found: dict[str, Mapping[str, Any]] = {}
        for start in range(
            0, len(ids), self.entity_batch_size if props != "labels" else LABEL_BATCH_SIZE
        ):
            size = self.entity_batch_size if props != "labels" else LABEL_BATCH_SIZE
            chunk = ids[start : start + size]
            body = await self._read(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": props,
                    "languages": "|".join(LANGUAGES),
                }
            )
            entities = body.get("entities")
            if not isinstance(entities, Mapping):
                raise ProviderPayloadError("Wikidata returned no entities")
            for key, entity in entities.items():
                if isinstance(entity, Mapping) and "missing" not in entity:
                    found[key] = entity
        return found

    # -- turning an entity into a candidate ------------------------------------------

    def _linked_ids(self, entities: Sequence[Mapping[str, Any]]) -> list[str]:
        """Every linked value whose label a candidate needs, once, in first-seen order.

        The cast is bounded *here* rather than after the lookup, so a film with thirty-one
        credits does not spend the label batch on people nobody will read.
        """
        seen: dict[str, None] = {}
        for entity in entities:
            claims = entity.get("claims")
            if not isinstance(claims, Mapping):
                continue
            for prop, limit in (
                (P_DIRECTOR, None),
                (P_COUNTRY, None),
                (P_ORIGINAL_LANGUAGE, None),
                (P_GENRE, None),
                (P_CAST, MAX_CAST),
            ):
                for value in _entity_ids(claims, prop, limit=limit):
                    seen.setdefault(value, None)
        return list(seen)[:LABEL_BATCH_SIZE]

    def _candidate(
        self, entity: Mapping[str, Any], labels: Mapping[str, Mapping[str, Any]]
    ) -> SearchCandidate | None:
        entity_id = entity.get("id")
        claims = entity.get("claims")
        if not isinstance(entity_id, str) or not isinstance(claims, Mapping):
            return None
        title = _localized(entity.get("labels"))
        if title is None:
            return None
        # The search filter already asks for films, but a `Q` id pasted into the add box
        # has been through no filter at all. A person, a novel or a television series is
        # a legible thing to paste and is not something this domain can hold.
        if not _is_film(claims):
            return None

        def named(prop: str, limit: int | None = None) -> list[str]:
            names = []
            for value in _entity_ids(claims, prop, limit=limit):
                label = _localized(labels.get(value, {}).get("labels"))
                if label:
                    names.append(label)
            return names

        directors = named(P_DIRECTOR)
        metadata: dict[str, Any] = {
            "creators": directors,
            "original_title": _monolingual(claims, P_ORIGINAL_TITLE),
            "countries": named(P_COUNTRY),
            "languages": named(P_ORIGINAL_LANGUAGE),
            "genres": named(P_GENRE),
            "runtime": _minutes(claims),
            "cast": named(P_CAST, MAX_CAST),
            "description": _localized(entity.get("descriptions")),
        }
        identifiers: dict[str, str] = {"wikidata": entity_id}
        for kind, (prop, pattern) in IDENTITY_CLAIMS.items():
            value = _external_id(claims, prop, pattern)
            if value is not None:
                identifiers[kind] = value
        return SearchCandidate(
            source=self.name,
            source_id=entity_id,
            source_refs=(SourceRef(self.name, entity_id),),
            title=title,
            subtitle=None,
            creators=tuple(directors),
            year=_year(claims),
            # Never a cover. `P18` is a general image property and the one measured
            # value was a set photograph rather than poster art (DEC-098).
            cover_url=None,
            identifiers=identifiers,
            language=None,
            metadata={key: value for key, value in metadata.items() if value not in (None, [], "")},
            # A director is a person and inverts, unlike an animation studio, so the
            # shared DEC-051 heuristic is left to do its job.
            creator_sort=None,
        )

    async def _candidates(self, ids: Sequence[str]) -> list[SearchCandidate]:
        entities = await self._entities(ids, "labels|descriptions|claims")
        ordered = [entities[value] for value in ids if value in entities]
        if not ordered:
            return []
        linked = self._linked_ids(ordered)
        labels = await self._entities(linked, "labels") if linked else {}
        rows = [self._candidate(entity, labels) for entity in ordered]
        found = [row for row in rows if row is not None]
        return [
            replace(row, cover_url=await poster_for(row.identifiers, self.posters)) for row in found
        ]

    # -- the Provider protocol --------------------------------------------------------

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        """Films only, in the order Wikidata ranked them.

        The film filter is not a nicety: without it the 1927 `Metropolis` was tenth,
        behind a record label, a novel and several games (DEC-098).
        """
        wanted = max(1, min(limit, MAX_SEARCH_RESULTS))
        ids = await self._search_ids(f"{query} {FILM_FILTER}", wanted)
        return (await self._candidates(ids[:wanted]))[:wanted]

    async def fetch(self, source_id: str) -> ItemPayload:
        """A film by `Q` id, or by an exact IMDb, TMDB or Letterboxd claim.

        Only Wikidata is registered, so a link to one of the other three resolves through
        the claim Wikidata already holds rather than through a scrape of a site we have
        no adapter for.
        """
        value = source_id.strip()
        for kind, (prop, pattern) in IDENTITY_CLAIMS.items():
            prefix = f"{kind}:"
            if value.startswith(prefix):
                raw = value[len(prefix) :].strip()
                if kind == "letterboxd":
                    raw = await self.resolve_letterboxd_slug(raw)
                if not pattern.fullmatch(raw):
                    raise ProviderPayloadError(f"{raw!r} is not a {kind} film identifier")
                return await self._fetch_by_claim(kind, prop, raw)
        if not _Q_ID.fullmatch(value):
            raise ProviderPayloadError(f"{source_id!r} is not a Wikidata entity id")
        return await self._fetch_entity(value)

    async def _fetch_entity(self, entity_id: str) -> ItemPayload:
        rows = await self._candidates([entity_id])
        if not rows:
            raise ProviderPayloadError(
                f"Wikidata has no usable film at {entity_id}", code="record_not_found"
            )
        return ItemPayload(**vars(rows[0]))

    async def _fetch_by_claim(self, kind: str, prop: str, value: str) -> ItemPayload:
        """Resolve an exact claim to one film, or refuse.

        Two answers is an ambiguity and zero is a miss. Neither is ever settled by
        falling back to a title, which is the whole point of asking by identity.

        The entity is then checked to actually carry the value it was found by: the
        search index is a derived copy, and a film that does not hold the claim is not
        the film that was asked for.
        """
        found = await self._search_ids(f"haswbstatement:{prop}={value}", 2)
        if not found:
            raise ProviderPayloadError(
                f"No film on Wikidata carries the {kind} identifier {value!r}",
                code="record_not_found",
            )
        if len(found) > 1:
            raise ProviderPayloadError(
                f"{len(found)} films carry the {kind} identifier {value!r}",
                code="identity_ambiguous",
            )
        payload = await self._fetch_entity(found[0])
        if payload.identifiers.get(kind) != value:
            raise ProviderPayloadError(
                f"{found[0]} does not carry the {kind} identifier {value!r}",
                code="record_not_found",
            )
        return payload

    async def fetch_by_identifier(self, kind: str, value: str) -> ItemPayload:
        """Background enrichment's entry point (DEC-067 row 3).

        The movie domain's declared key is `letterboxd`, and it arrives in two shapes: a
        bare `P6127` slug for a film added through search, and the short `boxd.it` URI a
        Letterboxd export stores. Both name one film, so both are accepted.
        """
        if kind != "letterboxd":
            raise ProviderPayloadError(
                f"Wikidata's movie adapter cannot look a film up by {kind!r}",
                code="unsupported_identity_kind",
            )
        return await self.fetch(f"letterboxd:{value.strip()}")

    # -- Letterboxd identity, and nothing else ----------------------------------------

    async def resolve_letterboxd_slug(self, value: str) -> str:
        """The film slug behind a Letterboxd address, resolved without reading a page.

        A `letterboxd.com/film/<slug>/` URL is already the answer. A short `boxd.it` URI
        is followed with **HEAD requests only**, through a small bound, and accepted only
        when it lands on an HTTPS Letterboxd film page. The body is never requested and
        never parsed: reading the destination's HTML for metadata would cross the
        provider and terms boundary this design deliberately avoids.
        """
        candidate = value.strip()
        if not candidate:
            raise ProviderPayloadError("A Letterboxd film identifier is required")
        if "/" not in candidate:
            return candidate
        for _hop in range(MAX_SHORT_URI_REDIRECTS):
            slug = _letterboxd_film_slug(candidate)
            if slug is not None:
                return slug
            if not _is_short_uri(candidate):
                raise ProviderPayloadError(
                    f"{candidate!r} is not a Letterboxd film address", code="unsafe_redirect"
                )
            candidate = await self._one_hop(candidate)
        raise ProviderPayloadError("Letterboxd redirected too many times", code="unsafe_redirect")

    async def _one_hop(self, url: str) -> str:
        await self._paced.wait()
        try:
            response = await self.client.head(url, follow_redirects=False)
        except httpx.HTTPError as error:
            raise ProviderPayloadError(
                "Letterboxd could not be reached", code="provider_unreachable"
            ) from error
        location = str(response.headers.get("location", "")).strip()
        if response.status_code not in {301, 302, 303, 307, 308} or not location:
            raise ProviderPayloadError(
                f"{url!r} did not redirect to a film page", code="unsafe_redirect"
            )
        return location


def _is_short_uri(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and (parsed.hostname or "").casefold() in _SHORT_URI_HOSTS


def _letterboxd_film_slug(value: str) -> str | None:
    """The slug in an HTTPS Letterboxd film URL, or `None` for anything else.

    Deliberately strict about scheme and host: a redirect is exactly where a destination
    can be swapped, and a plaintext hop is where it can be swapped by somebody else.
    """
    parsed = urlsplit(value)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in _LETTERBOXD_HOSTS:
        return None
    match = _LETTERBOXD_FILM_PATH.fullmatch(parsed.path)
    return match.group(1) if match else None
