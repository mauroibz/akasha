"""Every metadata provider this build can construct (Sprint 088, out of `create_app`)."""

import logging
from typing import Any

from book_tracker.config import Settings
from book_tracker.domain.providers import Provider
from book_tracker.domains.album.providers import MusicBrainzProvider
from book_tracker.domains.anime.providers import AniListProvider, KitsuProvider
from book_tracker.domains.book.providers import GoogleBooksProvider, OpenLibraryProvider
from book_tracker.domains.movie.cinemeta import CinemetaMovieProvider
from book_tracker.domains.movie.providers import WikidataMovieProvider
from book_tracker.domains.series.cinemeta import CinemetaSeriesProvider
from book_tracker.domains.series.providers import WikidataSeriesProvider
from book_tracker.domains.series.tvmaze import TvmazeSeriesProvider


def build_provider_catalog(provider_client: Any, configured: Settings) -> list[Provider]:
    # Every provider this build knows how to construct, wired or not. Provider
    # wiring is one of the three registration points a domain is allowed to share
    # (technical spec 6.6); what must not be shared is any *other* layer knowing a
    # provider's name, which is why `/api/health/providers` reads this catalog
    # rather than a list of its own (DEC-067 row 5).
    catalog: list[Provider] = [
        OpenLibraryProvider(
            provider_client, configured.user_agent_contact or "local@example.invalid"
        )
    ]
    google = GoogleBooksProvider(provider_client, configured.google_books_api_key)
    catalog.append(google)
    if not google.enabled:
        # Silently running on one provider is how search lost its Spanish-language
        # coverage without anyone noticing (product spec 4.2, DEC-024).
        logging.getLogger(__name__).warning(
            "GOOGLE_BOOKS_API_KEY is not set; search and enrichment run on Open "
            "Library alone and Spanish-language coverage will be poor"
        )
    # The album domain. MusicBrainz needs no key, only a descriptive User-Agent and
    # ~1 request/second, both of which the adapter owns (DEC-052 seam 4/6).
    catalog.append(
        MusicBrainzProvider(
            provider_client, configured.user_agent_contact or "local@example.invalid"
        )
    )
    # The anime domain. Neither provider needs a key, and both were measured rather
    # than chosen from documentation (DEC-088). AniList is primary; Kitsu is the
    # second opinion and the hedge, so a build that lost one still has a domain.
    # The User-Agent is not courtesy here: AniList answers 403 without it.
    catalog.extend(
        (
            AniListProvider(
                provider_client, configured.user_agent_contact or "local@example.invalid"
            ),
            KitsuProvider(
                provider_client, configured.user_agent_contact or "local@example.invalid"
            ),
        )
    )
    # The movie domain. Wikidata needs no key either: a descriptive User-Agent, a
    # `maxlag` tolerance and small bounded reads are the whole contract (DEC-098).
    # It is deliberately the only movie provider — TMDB's six-month cache term is
    # incompatible with this application's permanent, owner-editable metadata.
    catalog.append(
        WikidataMovieProvider(
            provider_client, configured.user_agent_contact or "local@example.invalid"
        )
    )
    # The series domain. Same keyless Wikidata contract as movies (DEC-098), with
    # the five-class search filter DEC-104 measured — the movie shape misses
    # animated series, anime series and miniseries outright. Registered as
    # `wikidata-series`: the catalog is keyed by name, and a second `wikidata`
    # would silently replace the movie adapter.
    catalog.append(
        WikidataSeriesProvider(
            provider_client, configured.user_agent_contact or "local@example.invalid"
        )
    )
    # TVmaze is the series domain's second source (DEC-104): a real synopsis, a
    # real airing status, and the shows Wikidata's title search misses. Keyless
    # like Wikidata, CC BY-SA — the credit line is DEC-105's deliverable. It
    # merges through the shared layer on the IMDb id; no fallback path is written.
    catalog.append(
        TvmazeSeriesProvider(
            provider_client, configured.user_agent_contact or "local@example.invalid"
        )
    )
    # Cinemeta is the third source for both movies and series (Sprint 063): Stremio's
    # keyless, IMDb-keyed metadata service, already a de facto dependency through
    # every poster this build renders (DEC-103). Ranked last in both domains'
    # `source_preference` — complementary and a fallback, never primary.
    catalog.append(
        CinemetaMovieProvider(
            provider_client, configured.user_agent_contact or "local@example.invalid"
        )
    )
    catalog.append(
        CinemetaSeriesProvider(
            provider_client, configured.user_agent_contact or "local@example.invalid"
        )
    )
    return catalog
