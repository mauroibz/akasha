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

SourceFactory = Callable[[Settings, Any], RecommendationSource | NotConfigured]

#: Empty until a real source lands: TMDB in Sprint 134, a hosted model in 135, the
#: library's own embeddings in 136. The test-only `fake` source is registered by the
#: tests themselves and never built here.
SOURCE_FACTORIES: tuple[SourceFactory, ...] = ()


def build_source_registry(
    configured: Settings,
    provider_client: Any,
    factories: Sequence[SourceFactory] = SOURCE_FACTORIES,
) -> SourceRegistry:
    return SourceRegistry(factory(configured, provider_client) for factory in factories)
