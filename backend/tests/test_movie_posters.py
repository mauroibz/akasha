"""Where a film's poster comes from, and what it costs.

Sprint 046 shipped movies coverless because Wikidata has no posters, and the owner's
first real import made the consequence plain: a library of blank tiles. The measurements
these tests pin were taken live on 2026-08-28 — Stremio answered 14 of 14 films with no
key, and 49 of 50 films carrying a TMDB id also carry an IMDb id.

The expensive mistake available here is spending a TMDB request per film for an answer
Stremio already gave for free, so that is asserted rather than assumed.
"""

from __future__ import annotations

import httpx
import pytest

from book_tracker.domains.movie.posters import TmdbPosters, poster_for
from book_tracker.infrastructure.covers import ALLOWED_COVER_HOSTS, CoverError, prepare_cover
from book_tracker.infrastructure.posters import metahub_poster_url
from book_tracker.infrastructure.providers import create_provider_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TestTheKeylessSource:
    def test_a_poster_url_is_built_and_never_fetched(self) -> None:
        """The whole reason this is primary: a poster for every film costs no request."""
        assert (
            metahub_poster_url("tt0076786")
            == "https://images.metahub.space/poster/medium/tt0076786/img"
        )

    @pytest.mark.parametrize(
        "value", [None, "", "   ", "nm0000602", "0076786", "tt", "tt12", "'; DROP TABLE"]
    )
    def test_anything_that_is_not_an_imdb_id_gets_no_url(self, value: str | None) -> None:
        """The id lands in a URL, so a value that is not one must never reach it."""
        assert metahub_poster_url(value) is None

    def test_its_host_is_allowlisted(self) -> None:
        assert "images.metahub.space" in ALLOWED_COVER_HOSTS


class TestTheNarrowFallback:
    async def test_tmdb_answers_a_film_that_has_only_a_tmdb_id(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer test-token"
            return httpx.Response(200, json={"poster_path": "/abc.jpg"})

        client = create_provider_client(httpx.MockTransport(handler))
        posters = TmdbPosters(client, "test-token")
        assert await posters.poster_url("11906") == "https://image.tmdb.org/t/p/w500/abc.jpg"
        await client.aclose()

    async def test_without_a_token_it_answers_nothing_and_calls_nothing(self) -> None:
        """A missing token disables the fallback; it never fails anything."""

        def forbidden(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"unexpected call to {request.url}")

        client = create_provider_client(httpx.MockTransport(forbidden))
        assert await TmdbPosters(client, "").poster_url("11906") is None
        await client.aclose()

    async def test_a_provider_having_a_bad_day_is_not_an_error(self) -> None:
        """A poster is a nicety on a record that is already complete."""

        def broken(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"status_message": "boom"})

        client = create_provider_client(httpx.MockTransport(broken))
        assert await TmdbPosters(client, "test-token").poster_url("11906") is None
        await client.aclose()

    async def test_a_film_tmdb_has_no_poster_for_yields_nothing(self) -> None:
        def empty(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"poster_path": None})

        client = create_provider_client(httpx.MockTransport(empty))
        assert await TmdbPosters(client, "test-token").poster_url("11906") is None
        await client.aclose()

    def test_its_host_is_allowlisted(self) -> None:
        assert "image.tmdb.org" in ALLOWED_COVER_HOSTS


class TestChoosingBetweenThem:
    async def test_a_film_with_both_ids_never_spends_a_tmdb_request(self) -> None:
        """49 of 50 films are this case. Asking TMDB would buy a duplicate answer."""

        def forbidden(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"unexpected call to {request.url}")

        client = create_provider_client(httpx.MockTransport(forbidden))
        url = await poster_for(
            {"imdb": "tt0076786", "tmdb": "11906"}, TmdbPosters(client, "test-token")
        )
        assert url == "https://images.metahub.space/poster/medium/tt0076786/img"
        await client.aclose()

    async def test_a_film_with_only_a_tmdb_id_falls_back(self) -> None:
        """The ~2% the keyless source structurally cannot serve."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, json={"poster_path": "/xyz.jpg"})

        client = create_provider_client(httpx.MockTransport(handler))
        url = await poster_for({"tmdb": "11906"}, TmdbPosters(client, "test-token"))
        assert url == "https://image.tmdb.org/t/p/w500/xyz.jpg"
        assert len(calls) == 1
        await client.aclose()

    async def test_a_film_with_neither_id_gets_no_cover(self) -> None:
        assert await poster_for({"wikidata": "Q546900"}) is None

    async def test_with_no_fallback_configured_a_tmdb_only_film_is_coverless(self) -> None:
        """Which is the state it was in before this sprint, not a regression."""
        assert await poster_for({"tmdb": "11906"}) is None


class TestThroughTheCoverPipeline:
    """The bounds are not loosened for this. Both sources go through the same door."""

    async def test_a_miss_is_survivable_and_installs_nothing(self, tmp_path: object) -> None:
        """Stremio answers an unknown film with a clean 404 rather than a placeholder,
        which is what makes a built-not-fetched URL safe to hand the pipeline."""

        def missing(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="not found")

        client = create_provider_client(httpx.MockTransport(missing))
        url = metahub_poster_url("tt9999999")
        assert url is not None
        with pytest.raises(CoverError):
            await prepare_cover(client, url, tmp_path)  # type: ignore[arg-type]
        await client.aclose()

    async def test_a_poster_is_installed_through_the_shared_bounds(self, tmp_path: object) -> None:
        """A 500x750 WebP is what the service actually returns, and it clears the
        minimum edge, the aspect guard and the byte ceiling unchanged."""
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (500, 750), (40, 40, 60)).save(buffer, format="WEBP")
        body = buffer.getvalue()

        def poster(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "image/webp"})

        client = create_provider_client(httpx.MockTransport(poster))
        url = metahub_poster_url("tt0076786")
        assert url is not None
        prepared = await prepare_cover(client, url, tmp_path)  # type: ignore[arg-type]
        with Image.open(prepared) as image:
            # Downscaled to the shared 600 long edge, never upscaled.
            assert max(image.size) == 600
        await client.aclose()

    async def test_a_host_nobody_allowlisted_is_still_refused(self, tmp_path: object) -> None:
        client = create_provider_client(httpx.MockTransport(lambda r: httpx.Response(200)))
        with pytest.raises(CoverError):
            await prepare_cover(
                client,
                "https://posters.evil.test/poster.jpg",
                tmp_path,  # type: ignore[arg-type]
            )
        await client.aclose()
