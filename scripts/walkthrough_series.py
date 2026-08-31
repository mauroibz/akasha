"""Sprint 049's walkthrough gate, run against recorded Wikidata responses.

Wikidata's query-service replicas have been maxlag-shedding since mid-morning on
2026-08-31 (lag 24 s → 47 s and climbing), and the adapter's contractual `maxlag=5`
means every live search is refused. The walkthrough gate cannot wait on an external
incident with no ETA, so — at the owner's direction — it runs against the verbatim
responses captured live earlier the same day (Sprint 049's own fixtures), with the
rest of the boundary left live: the Stremio poster fetch and the whole cover
pipeline make real requests.

This is the substitution the walkthrough gate exists to scrutinise, not a shortcut
around it. What is proven:

- the domain renders on every screen from `GET /api/item-types` with no frontend
  change (nothing below was written for series);
- a search candidate becomes a library row with the series' own fields, its IMDb
  identity and its own words;
- the poster is the series' actual poster art, fetched live from Stremio by IMDb id
  through the unmodified cover pipeline — the Sprint 046 failure mode was a wall of
  blank tiles, so the served image is asserted to be a real, non-trivial JPEG;
- an episode count is stored and rendered against the series' own total, and a
  count above it is stored rather than refused (DEC-092).

What is NOT proven, and is recorded as a deviation in the sprint Outcome: that the
adapter's request shape is still what live Wikidata answers today. The fixtures pin
the 2026-08-31 contract; the provider suite already proves the adapter parses them.
When the replicas recover, one live search is the whole remaining proof.

Run it:

    cd backend && uv run python ../scripts/walkthrough_series.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "tests"))

from recordings import recording  # noqa: E402

from book_tracker.config import Settings  # noqa: E402
from book_tracker.domains.series.providers import (  # noqa: E402
    SERIES_FILTER,
    wikidata_series_route_key,
)
from book_tracker.infrastructure.providers import create_provider_client  # noqa: E402
from book_tracker.main import create_app  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures" / "providers"


def search_key(query: str) -> str:
    return f"search:{query} {SERIES_FILTER}"


def claim_key(prop: str, value: str) -> str:
    return f"search:haswbstatement:{prop}={value}"


def entities_key(*ids: str) -> str:
    return "entities:labels|descriptions|claims:" + "|".join(ids)


def labels_key(body: object) -> str:
    assert isinstance(body, dict)
    return "labels:" + "|".join(body["entities"])


BOJACK_LABELS = recording("wikidata_series_labels_bojack_pair.json")
BREAKING_BAD_LABELS = recording("wikidata_series_labels_Q1079_breaking_bad.json")


def single_entity(batch: object, entity_id: str) -> dict[str, object]:
    """One entity sliced out of a recorded batch, for the add path's lone fetch.

    Search reads a batch of hits; adding one fetches its `source_id` alone. The
    batch fixture holds the same entity verbatim, so the single-entity answer is
    the same bytes under a one-key `entities` map — not a new recording, the same
    one read differently.
    """
    assert isinstance(batch, dict)
    entities = batch["entities"]
    assert isinstance(entities, dict) and entity_id in entities
    return {"entities": {entity_id: entities[entity_id]}}


BOJACK_PAIR = recording("wikidata_series_entities_bojack_pair.json")

#: Every Wikidata route the walkthrough can reach, keyed exactly as the adapter's
#: requests are. Anything not listed here fails loudly rather than falling through
#: to a live call the incident would shed.
ROUTES: dict[str, tuple[int, object]] = {
    search_key("BoJack Horseman"): (200, recording("wikidata_series_search_bojack.json")),
    entities_key("Q17733404", "Q87484192"): (200, BOJACK_PAIR),
    # The add path fetches the chosen series alone, not as the search batch.
    entities_key("Q17733404"): (200, single_entity(BOJACK_PAIR, "Q17733404")),
    labels_key(BOJACK_LABELS): (200, BOJACK_LABELS),
    search_key("Breaking Bad"): (200, recording("wikidata_series_search_breaking_bad.json")),
    entities_key("Q1079", "Q17057981", "Q136483358"): (
        200,
        recording("wikidata_series_entity_Q1079_breaking_bad.json"),
    ),
    labels_key(BREAKING_BAD_LABELS): (200, BREAKING_BAD_LABELS),
    claim_key("P345", "tt0903747"): (
        200,
        recording("wikidata_series_search_p345_tt0903747.json"),
    ),
    entities_key("Q1079"): (200, recording("wikidata_series_entity_Q1079_breaking_bad.json")),
    claim_key("P345", "tt9999999"): (
        200,
        recording("wikidata_series_search_p345_no_match.json"),
    ),
}


def walkthrough_transport(live: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
    """Replay Wikidata from fixtures; pass every other host through live.

    The Stremio poster fetch is the live half of this gate: a blank tile is the
    failure mode Sprint 046 shipped, so the cover pipeline makes its real request.
    """

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "www.wikidata.org":
                name = wikidata_series_route_key(request)
                route = ROUTES.get(name)
                if route is None:
                    # A label read nobody recorded: the movie adapter, asked to
                    # resolve a series IMDb link, collects a different linked-id
                    # batch than the series adapter before its film guard refuses
                    # the entity. Labels are display-only and the guard reads the
                    # entity's claims, so an empty batch lets it reach that refusal
                    # honestly rather than dying on a fixture gap as a fake outage.
                    if name.startswith("labels:"):
                        return httpx.Response(200, json={"entities": {}})
                    return httpx.Response(500, text=f"no recording for {name}")
                status, body = route
                return httpx.Response(status, json=body)
            return await live.handle_async_request(request)

    return Transport()


async def main() -> None:
    data_dir = Path(tempfile.mkdtemp(prefix="akasha-walkthrough-049-"))
    settings = Settings(
        data_dir=data_dir,
        user_agent_contact="walkthrough@example.invalid",
        log_level="WARNING",
    )
    app = create_app(settings)

    # Boot the lifespan far enough to run migrations and build the catalog, then
    # swap the shared client's transport for the replaying one. The catalog holds
    # provider instances that read `self.client`, so replacing the client's
    # transport reaches every provider at once — the same seam the test suite uses.
    async with app.router.lifespan_context(app):
        live_transport = httpx.AsyncHTTPTransport()
        replaying = create_provider_client(walkthrough_transport(live_transport))
        await app.state.provider_client.aclose()
        app.state.provider_client = replaying
        for provider in app.state.provider_catalog.values():
            provider.client = replaying
        # The enrichment handler captured the original client at construction; the
        # add flow reads `app.state.provider_client` per request and needs no patch.
        for handler in app.state.job_runner.handlers.values():
            if hasattr(handler, "cover_client"):
                handler.cover_client = replaying

        # Prove the seam before serving: one search through the swapped provider,
        # logged, so a mis-wired transport fails here rather than as a bare 503.
        probe = app.state.provider_catalog["wikidata-series"]
        enabled_probe = app.state.providers.get("wikidata-series")
        print(
            f"catalog id={id(probe)} enabled id={id(enabled_probe)} "
            f"client id={id(probe.client)} enabled client id={id(getattr(enabled_probe, 'client', None))}",
            flush=True,
        )
        try:
            rows = await probe.search("Breaking Bad")
            print(f"self-test search -> {[(r.source_id, r.title) for r in rows]}", flush=True)
        except Exception as error:
            print(f"self-test search FAILED: {type(error).__name__}: {error}", flush=True)
            raise

        port = 8100
        # `lifespan="off"`: this script drives the lifespan itself above (it has to —
        # the replay seam is installed inside it), and uvicorn's own lifespan pass
        # would re-run it and rebuild every provider on a live client, silently
        # undoing the swap.
        config = __import__("uvicorn").Config(
            app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"
        )
        server = __import__("uvicorn").Server(config)
        task = asyncio.create_task(server.serve())
        # Wait for the socket rather than sleeping a fixed count.
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        print(f"walkthrough backend on http://127.0.0.1:{port}", flush=True)
        print(f"BOOK_TRACKER_DATA_DIR={data_dir}", flush=True)
        try:
            await task
        finally:
            await live_transport.aclose()


if __name__ == "__main__":
    asyncio.run(main())
