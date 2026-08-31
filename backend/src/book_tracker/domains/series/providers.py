"""Series' adapter: Wikidata's official Action API, and nothing else.

Structurally the movie adapter (DEC-098), with one difference that is the whole reason
this is not a copy: the search filter is **five instance-of classes, not one**. A
single `P31=Q5398426` filter — the movie shape — returned the right series at rank 1
for only 9 of 14 measured titles and returned *nothing at all* for `Chainsaw Man` and
`Rick and Morty` (measured 2026-08-31, DEC-104; docs/series-domain-viability.md).

Everything DEC-099 established carries over unchanged: bounded search then bounded
entity batches, `maxlag`, a descriptive User-Agent, and re-checking a claim on the
fetched entity rather than trusting a `haswbstatement` hit. Series entities are
**larger** than films — thirteen measured 1.37 MB, one of them 105 KB alone — so the
batch size is no larger than the movie adapter's and the response bound is not raised.

Nothing raw leaves this module: not a provider row, and not an `httpx` exception.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl

import httpx

from book_tracker.domain.providers import ItemPayload, SearchCandidate, SourceRef
from book_tracker.infrastructure.posters import metahub_poster_url
from book_tracker.infrastructure.providers import (
    INTERACTIVE_ATTEMPTS,
    ProviderPayloadError,
    bounded_json,
)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "Akasha/1.4 ({contact})"

#: The five instance-of classes a television series is filed under. A single
#: `P31=Q5398426` filter — the movie adapter's shape, copied — returned the right
#: series at rank 1 for only 9 of 14 measured titles and returned *nothing at all*
#: for `Chainsaw Man` and `Rick and Morty` (measured 2026-08-31, DEC-104;
#: docs/series-domain-viability.md). This is a live measurement with a shelf life:
#: if a later series is missed, add a measured class here rather than widening the
#: filter speculatively.
SERIES_FILTER = "haswbstatement:P31=Q5398426|P31=Q117467246|P31=Q63952888|P31=Q1259759|P31=Q581714"

#: The five classes as a set, for the fetched-entity guard: a `Q` id pasted into the
#: add box has been through no filter at all, and a film, a person or a novel is not
#: something this domain can hold.
SERIES_CLASSES = frozenset({"Q5398426", "Q117467246", "Q63952888", "Q1259759", "Q581714"})

# Wikimedia asks clients to use `maxlag` so a replica that has fallen behind sheds load
# rather than serving stale reads. Five seconds is the value their own guidance suggests
# for interactive clients.
MAXLAG_SECONDS = 5
# Measured 2026-08-31: thirteen series entities weighed 1.37 MB — larger than films,
# one of them 105 KB alone. `MAX_PROVIDER_BYTES` is 2 MiB, so three at a time leaves
# real headroom for a series with an unusually long claim list, exactly as for films.
ENTITY_BATCH_SIZE = 3
# Six bounded entity reads is already four requests for one search. The class filter
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

# The claims a series is read from. Everything else on the entity is ignored.
P_INSTANCE_OF = "P31"
P_CREATOR = "P170"
P_SCREENWRITER = "P58"
P_COUNTRY = "P495"
P_ORIGINAL_LANGUAGE = "P364"
P_GENRE = "P136"
P_EPISODES = "P1113"
P_SEASONS = "P2437"
P_DURATION = "P2047"
P_NETWORK = "P449"
P_START_TIME = "P580"
P_END_TIME = "P582"
P_CAST = "P161"
P_ORIGINAL_TITLE = "P1476"
P_IMDB = "P345"
P_TMDB_SERIES = "P4983"
P_TVDB = "P4835"

_UNIT_MINUTE = "Q7727"
_UNIT_SECOND = "Q11574"

#: Which stored identifier kind comes from which claim, and what a valid value looks
#: like. The pattern is what stops a typo in a paste from becoming an exact lookup.
#: TVDB series ids on Wikidata are numeric (measured on the captured entities); the
#: slug a `thetvdb.com/series/<slug>` URL carries is **not** this claim, so a TVDB URL
#: cannot resolve through it and is refused honestly rather than guessed.
IDENTITY_CLAIMS: Mapping[str, tuple[str, re.Pattern[str]]] = {
    "imdb": (P_IMDB, re.compile(r"tt[0-9]{7,10}")),
    "tmdb": (P_TMDB_SERIES, re.compile(r"[0-9]{1,12}")),
}

_Q_ID = re.compile(r"Q[1-9][0-9]*")
_YEAR = re.compile(r"^[+-]?(\d{4})")

#: Spanish first, English as the fallback. Both were present on every measured entity
#: and on all of their linked values, so this is a preference rather than a hope
#: (DEC-104; Spanish descriptions are full sentences).
LANGUAGES = ("es", "en")


def wikidata_series_route_key(request: httpx.Request) -> str:
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
    marked wrong, and a `preferred` one is the answer among several that are all
    defensible. Reading the first element of the list gets both of those backwards.
    """
    live = [row for row in statements if row.get("rank") != "deprecated"]
    return [row for row in live if row.get("rank") == "preferred"] or live


def _value(statement: Mapping[str, Any]) -> Any | None:
    """The snak's value, or `None` for `somevalue` and `novalue`."""
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
    that kind resolve to somebody else's series.
    """
    for statement in _best(_statements(claims, prop)):
        value = _value(statement)
        if isinstance(value, str) and pattern.fullmatch(value.strip()):
            return value.strip()
    return None


def _quantity(claims: Mapping[str, Any], prop: str) -> int | None:
    """A bare count — episodes, seasons — read as a whole number."""
    for statement in _best(_statements(claims, prop)):
        value = _value(statement)
        if not isinstance(value, Mapping):
            continue
        amount = str(value.get("amount") or "").lstrip("+")
        try:
            number = float(amount)
        except ValueError:
            continue
        if number >= 1 and number == int(number):
            return int(number)
    return None


def _year(claims: Mapping[str, Any]) -> int | None:
    """The earliest best-ranked start year.

    A series' neutral year is its start time (`P580`), present on 13/13 measured
    entities. Precision below `9` is a decade or coarser and says nothing about a year.
    The date is read as text on purpose: month-precision Wikidata timestamps carry day
    zero and no date parser will accept them.
    """
    years: list[int] = []
    for statement in _best(_statements(claims, P_START_TIME)):
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
    """An episode length, read with its unit rather than as a bare number."""
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


def _airing_status(claims: Mapping[str, Any]) -> str | None:
    """`Running` or `Ended`, derived from the presence of an end-time claim.

    Wikidata expresses an airing state only as the presence or absence of `P582`;
    TVmaze replaces this derivation with a real status in Sprint 050.
    """
    if not _statements(claims, P_START_TIME):
        return None
    return "Ended" if _best(_statements(claims, P_END_TIME)) else "Running"


def _is_series(claims: Mapping[str, Any]) -> bool:
    return bool(SERIES_CLASSES & set(_entity_ids(claims, P_INSTANCE_OF)))


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


class WikidataSeriesProvider:
    """The series domain's one adapter in this sprint (DEC-104). Keyless, CC0.

    Registered as `wikidata-series` rather than `wikidata`: the provider catalog is
    keyed by name, and a second adapter answering to `wikidata` would silently replace
    the movie domain's.
    """

    name = "wikidata-series"
    item_type = "series"

    def __init__(
        self,
        client: httpx.AsyncClient,
        contact: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        min_interval_seconds: float = MIN_INTERVAL_SECONDS,
        entity_batch_size: int = ENTITY_BATCH_SIZE,
    ) -> None:
        self.client = client
        self.contact = contact
        self.entity_batch_size = max(1, entity_batch_size)
        self._paced = _Paced(min_interval_seconds, sleep)

    # -- the boundary ---------------------------------------------------------------

    async def _read(self, params: Mapping[str, str | int]) -> Mapping[str, Any]:
        """One paced, retrying, bounded read. Every call to Wikidata goes through here."""
        await self._paced.wait()
        try:
            body = await bounded_json(
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

        The cast is bounded *here* rather than after the lookup, so a series with a
        hundred credits does not spend the label batch on people nobody will read.
        """
        seen: dict[str, None] = {}
        for entity in entities:
            claims = entity.get("claims")
            if not isinstance(claims, Mapping):
                continue
            for prop, limit in (
                (P_CREATOR, None),
                (P_SCREENWRITER, None),
                (P_COUNTRY, None),
                (P_ORIGINAL_LANGUAGE, None),
                (P_GENRE, None),
                (P_NETWORK, None),
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
        # The search filter already asks for series, but a `Q` id pasted into the add
        # box has been through no filter at all. A film, a person or a novel is a
        # legible thing to paste and is not something this domain can hold.
        if not _is_series(claims):
            return None

        def named(prop: str, limit: int | None = None) -> list[str]:
            names = []
            for value in _entity_ids(claims, prop, limit=limit):
                label = _localized(labels.get(value, {}).get("labels"))
                if label:
                    names.append(label)
            return names

        # The creator is the name a series is filed under; `P57` (director) was present
        # on a minority of measured entities. Screenwriters are the measured fallback.
        creators = _entity_ids(claims, P_CREATOR) or _entity_ids(claims, P_SCREENWRITER)
        creator_names = [
            label
            for value in creators
            if (label := _localized(labels.get(value, {}).get("labels")))
        ]
        network = named(P_NETWORK)
        metadata: dict[str, Any] = {
            "creators": creator_names,
            "original_title": _monolingual(claims, P_ORIGINAL_TITLE),
            "countries": named(P_COUNTRY),
            "languages": named(P_ORIGINAL_LANGUAGE),
            "genres": named(P_GENRE),
            "episodes": _quantity(claims, P_EPISODES),
            "seasons": _quantity(claims, P_SEASONS),
            "episode_minutes": _minutes(claims),
            "network": network[0] if network else None,
            "airing_status": _airing_status(claims),
            "cast": named(P_CAST, MAX_CAST),
            "synopsis": _localized(entity.get("descriptions")),
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
            creators=tuple(creator_names),
            year=_year(claims),
            # Keyless and deterministic: a poster for every series with an IMDb id
            # costs no request (DEC-103, DEC-104). A series without one is coverless,
            # exactly as it was before.
            cover_url=metahub_poster_url(identifiers.get("imdb")),
            identifiers=identifiers,
            language=None,
            metadata={key: value for key, value in metadata.items() if value not in (None, [], "")},
            # A creator is a person and inverts, unlike an animation studio, so the
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
        return [row for row in rows if row is not None]

    # -- the Provider protocol --------------------------------------------------------

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        """Series only, in the order Wikidata ranked them.

        The five-class filter is not a nicety: under the movie adapter's single-class
        shape, `Chainsaw Man` and `Rick and Morty` returned nothing at all (DEC-104).
        """
        wanted = max(1, min(limit, MAX_SEARCH_RESULTS))
        ids = await self._search_ids(f"{query} {SERIES_FILTER}", wanted)
        return (await self._candidates(ids[:wanted]))[:wanted]

    async def fetch(self, source_id: str) -> ItemPayload:
        """A series by `Q` id, or by an exact IMDb or TMDB series claim.

        Only Wikidata is registered, so a link to one of the other catalogues resolves
        through the claim Wikidata already holds rather than through a scrape of a site
        we have no adapter for. A TVDB slug or a TVmaze id names no Wikidata claim this
        sprint measures, so both are refused honestly rather than guessed; Sprint 050's
        TVmaze adapter is where a TVmaze id becomes resolvable.
        """
        value = source_id.strip()
        for prefix in ("tvdb:", "tvmaze:"):
            if value.startswith(prefix):
                raise ProviderPayloadError(
                    f"A {prefix[:-1]} identifier names no Wikidata claim yet; "
                    "it becomes resolvable with Sprint 050's TVmaze adapter",
                    code="record_not_found",
                )
        for kind, (prop, pattern) in IDENTITY_CLAIMS.items():
            prefix = f"{kind}:"
            if value.startswith(prefix):
                raw = value[len(prefix) :].strip()
                if not pattern.fullmatch(raw):
                    raise ProviderPayloadError(f"{raw!r} is not a {kind} series identifier")
                return await self._fetch_by_claim(kind, prop, raw)
        if not _Q_ID.fullmatch(value):
            raise ProviderPayloadError(f"{source_id!r} is not a Wikidata entity id")
        return await self._fetch_entity(value)

    async def _fetch_entity(self, entity_id: str) -> ItemPayload:
        rows = await self._candidates([entity_id])
        if not rows:
            raise ProviderPayloadError(
                f"Wikidata has no usable series at {entity_id}", code="record_not_found"
            )
        return ItemPayload(**vars(rows[0]))

    async def _fetch_by_claim(self, kind: str, prop: str, value: str) -> ItemPayload:
        """Resolve an exact claim to one series, or refuse.

        Two answers is an ambiguity and zero is a miss. Neither is ever settled by
        falling back to a title, which is the whole point of asking by identity.

        The entity is then checked to actually carry the value it was found by: the
        search index is a derived copy, and a series that does not hold the claim is
        not the series that was asked for.
        """
        found = await self._search_ids(f"haswbstatement:{prop}={value}", 2)
        if not found:
            raise ProviderPayloadError(
                f"No series on Wikidata carries the {kind} identifier {value!r}",
                code="record_not_found",
            )
        if len(found) > 1:
            raise ProviderPayloadError(
                f"{len(found)} series carry the {kind} identifier {value!r}",
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

        The series domain's declared key is `imdb`, which both planned importers carry
        as their primary identity. `haswbstatement:P345=` hit 13 of 13 measured series
        (docs/series-domain-viability.md); it is not optional.
        """
        if kind != "imdb":
            raise ProviderPayloadError(
                f"Wikidata's series adapter cannot look a series up by {kind!r}",
                code="unsupported_identity_kind",
            )
        return await self.fetch(f"imdb:{value.strip()}")
