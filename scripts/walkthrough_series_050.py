"""Sprint 050's walkthrough gate: TVmaze alongside Wikidata, against recorded responses.

Sprint 049 established the pattern: Wikidata's replicas were maxlag-shedding on
2026-08-31, so its half of the boundary replays that day's live fixtures. TVmaze's
half replays Sprint 050's own fixtures — captured live the same day — for the same
reason: the walkthrough must be deterministic, and the recorded responses are the
contract the provider suite already proves the adapter parses. The Stremio poster
fetch and the whole cover pipeline stay live, because a blank tile is the failure
mode Sprint 046 shipped.

What this gate proves that Sprint 049's did not:

- a series search reaches **both** providers and returns one merged list — the
  merged candidate carries TVmaze's synopsis, airing status and network on top of
  Wikidata's record, with nothing Wikidata supplied overwritten;
- a Spanish-language show Wikidata's title search does not surface — `Los
  Simuladores` — is found through TVmaze alone, with the correct premiere year;
- the credit line naming Wikidata and TVmaze is visible on the running
  application (AC9).

The merged-record case is `Breaking Bad`: both providers answer it, both carry
`imdb:tt0903747`, and the shared `merge_and_rank` groups them on that identity.
Wikidata wins the primary slot by source preference; TVmaze fills the fields
Wikidata left empty.

Run it:

    cd backend && uv run python ../scripts/walkthrough_series_050.py
"""

from __future__ import annotations

import asyncio
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


BREAKING_BAD_LABELS = recording("wikidata_series_labels_Q1079_breaking_bad.json")


def single_entity(batch: object, entity_id: str) -> dict[str, object]:
    """One entity sliced out of a recorded batch, for the add path's lone fetch."""
    assert isinstance(batch, dict)
    entities = batch["entities"]
    assert isinstance(entities, dict) and entity_id in entities
    return {"entities": {entity_id: entities[entity_id]}}


BB_ENTITY = recording("wikidata_series_entity_Q1079_breaking_bad.json")

#: Every Wikidata route the walkthrough can reach, keyed exactly as the adapter's
#: requests are. Anything not listed here fails loudly rather than falling through
#: to a live call the incident would shed.
WIKIDATA_ROUTES: dict[str, tuple[int, object]] = {
    search_key("Breaking Bad"): (200, recording("wikidata_series_search_breaking_bad.json")),
    entities_key("Q1079", "Q17057981", "Q136483358"): (200, BB_ENTITY),
    entities_key("Q1079"): (200, BB_ENTITY),
    labels_key(BREAKING_BAD_LABELS): (200, BREAKING_BAD_LABELS),
    claim_key("P345", "tt0903747"): (200, recording("wikidata_series_search_p345_tt0903747.json")),
    # Los Simuladores: Wikidata's title search does not surface it (AC2). A miss is
    # the honest answer, not an outage.
    search_key("Los Simuladores"): (200, {"query": {"search": [], "searchinfo": {"totalhits": 0}}}),
}


def tvmaze_route(request: httpx.Request) -> tuple[int, object] | None:
    """The TVmaze fixture for one request, or None to fail loudly."""
    path = request.url.path
    params = dict(parse_qsl(request.url.query.decode()))
    if path == "/search/shows":
        query = params.get("q", "")
        named = {
            "Breaking Bad": "tvmaze_search_breaking_bad.json",
            "Los Simuladores": "tvmaze_search_los_simuladores.json",
        }.get(query)
        return (200, recording(named)) if named else None
    if path == "/lookup/shows":
        imdb = params.get("imdb", "")
        named = {
            "tt0903747": "tvmaze_lookup_tt0903747.json",
            "tt0316613": "tvmaze_show_10577_los_simuladores.json",
        }.get(imdb)
        return (200, recording(named)) if named else None
    if path.startswith("/shows/"):
        named = {
            "/shows/169": "tvmaze_show_169_breaking_bad.json",
            "/shows/10577": "tvmaze_show_10577_los_simuladores.json",
        }.get(path)
        return (200, recording(named)) if named else None
    return None


def walkthrough_transport(live: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
    """Replay Wikidata and TVmaze from fixtures; pass every other host through live.

    The Stremio poster fetch is the live half of this gate: a blank tile is the
    failure mode Sprint 046 shipped, so the cover pipeline makes its real request.
    """

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "www.wikidata.org":
                name = wikidata_series_route_key(request)
                route = WIKIDATA_ROUTES.get(name)
                if route is None:
                    if name.startswith("labels:"):
                        return httpx.Response(200, json={"entities": {}})
                    return httpx.Response(500, text=f"no recording for {name}")
                status, body = route
                return httpx.Response(status, json=body)
            if request.url.host == "api.tvmaze.com":
                route = tvmaze_route(request)
                if route is None:
                    return httpx.Response(500, text=f"no recording for {request.url.path}")
                status, body = route
                return httpx.Response(status, json=body)
            return await live.handle_async_request(request)

    return Transport()


async def main() -> None:
    data_dir = Path(tempfile.mkdtemp(prefix="akasha-walkthrough-050-"))
    settings = Settings(
        data_dir=data_dir,
        user_agent_contact="walkthrough@example.invalid",
        log_level="WARNING",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        live_transport = httpx.AsyncHTTPTransport()
        replaying = create_provider_client(walkthrough_transport(live_transport))
        await app.state.provider_client.aclose()
        app.state.provider_client = replaying
        for provider in app.state.provider_catalog.values():
            provider.client = replaying
        for handler in app.state.job_runner.handlers.values():
            if hasattr(handler, "cover_client"):
                handler.cover_client = replaying

        # Prove the seam before serving: both providers answer one search.
        wikidata = app.state.provider_catalog["wikidata-series"]
        tvmaze = app.state.provider_catalog["tvmaze"]
        try:
            wikidata_rows = await wikidata.search("Breaking Bad")
            tvmaze_rows = await tvmaze.search("Breaking Bad")
            print(
                f"self-test wikidata -> {[(r.source_id, r.title) for r in wikidata_rows]}",
                flush=True,
            )
            print(
                f"self-test tvmaze -> {[(r.source_id, r.title) for r in tvmaze_rows]}",
                flush=True,
            )
        except Exception as error:
            print(f"self-test search FAILED: {type(error).__name__}: {error}", flush=True)
            raise

        port = 8101
        config = __import__("uvicorn").Config(
            app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"
        )
        server = __import__("uvicorn").Server(config)
        task = asyncio.create_task(server.serve())
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        print(f"walkthrough backend on http://127.0.0.1:{port}", flush=True)
        print(f"AKASHA_DATA_DIR={data_dir}", flush=True)
        try:
            await task
        finally:
            await live_transport.aclose()


if __name__ == "__main__":
    asyncio.run(main())
