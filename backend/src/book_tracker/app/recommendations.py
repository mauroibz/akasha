"""Every recommendation source this build can construct (Sprint 133, DEC-183 point 5).

The same registration model as `app/providers.py`: code, not a plugin runtime. A
factory reads its configuration and answers with the source, or with a
`NotConfigured` naming what is missing; the registry built from them is what rounds
ask by name. Which provider backs a source is this configuration, never a domain's.
"""

from collections.abc import Callable, Sequence
from typing import Any

from book_tracker.config import Settings
from book_tracker.domain.recommendations import (
    NotConfigured,
    RecommendationSource,
    SourceRegistry,
)
from book_tracker.infrastructure import model_recommendations as model
from book_tracker.infrastructure import tmdb_recommendations as tmdb
from book_tracker.infrastructure.model_clients import (
    DEFAULT_MODELS,
    PROVIDER_LABELS,
    build_model_client,
)

SourceFactory = Callable[[Settings, Any], RecommendationSource | NotConfigured]

#: Daily rounds a source answers unless `AKASHA_RECOMMEND_DAILY_LIMITS` names it. A
#: hosted model is paid per call, so it is held to fifty a day by default; TMDB is
#: free and unbounded here (its own rate limit is generous).
DEFAULT_RECOMMEND_LIMITS: dict[str, int] = {"model": 50}


def tmdb_source(configured: Settings, provider_client: Any) -> RecommendationSource | NotConfigured:
    """TMDB's recommendations, with `TMDB_READ_TOKEN` (Sprint 134)."""
    if not configured.tmdb_read_token.strip():
        return NotConfigured(
            tmdb.NAME,
            tmdb.NOT_CONFIGURED_HINT,
            retention=tmdb.RETENTION,
            label="TMDB",
            attribution=tmdb.TMDB_ATTRIBUTION,
        )
    return tmdb.TmdbRecommendations(provider_client, configured.tmdb_read_token.strip())


def model_source(
    configured: Settings, provider_client: Any
) -> RecommendationSource | NotConfigured:
    """A hosted model, by provider kind and API key (Sprint 135, DEC-187).

    `AKASHA_RECS_MODEL_PROVIDER` picks the API (Claude by default), `AKASHA_RECS_MODEL`
    the model (each kind has a default), and the key is `AKASHA_RECS_MODEL_KEY` or the
    provider's usual variable. No key: `not_configured`, saying how to set one.
    """
    provider = configured.recs_model_provider
    chosen = configured.recs_model.strip() or DEFAULT_MODELS[provider]
    key = configured.recs_model_secret()
    if not key:
        return NotConfigured(
            model.NAME,
            model.NOT_CONFIGURED_HINT,
            label=model.LABEL,
            resolved_only=True,
            about={
                "provider": provider,
                "provider_label": PROVIDER_LABELS[provider],
                "model": chosen,
                "sends": model.SENDS,
            },
        )
    client = build_model_client(provider_client, provider, key, chosen, configured.recs_model_url)
    return model.ModelRecommendations(client)


#: TMDB from Sprint 134, a hosted model from 135; the library's own embeddings in 136
#: join them. The test-only `fake` source is registered by the tests themselves and
#: never built here.
SOURCE_FACTORIES: tuple[SourceFactory, ...] = (tmdb_source, model_source)


def build_source_registry(
    configured: Settings,
    provider_client: Any,
    factories: Sequence[SourceFactory] = SOURCE_FACTORIES,
) -> SourceRegistry:
    return SourceRegistry(factory(configured, provider_client) for factory in factories)
