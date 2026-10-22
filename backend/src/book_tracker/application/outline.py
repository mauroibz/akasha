"""Fetching the outline progress marks are drawn against, when the owner asks (DEC-171).

A series added before 2.7 has no season list; a book's chapter count rarely arrives at
all. The outline action asks the domain's own enrichment providers, by the identities
the domain declares, for the one field its `ProgressSpec` draws from — and nothing
else. It is an explicit action, never part of rendering a page, and it never replaces
a value the item already holds: a chapter count the owner typed stays theirs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from functools import partial
from typing import Any

from book_tracker.application.library import LibraryError
from book_tracker.domain.spec import Domain
from book_tracker.infrastructure.providers import ProviderPayloadError


def outline_field(domain: Domain) -> str | None:
    """The metadata field an outline is read from: the parts, else the total."""
    if domain.progress is None:
        return None
    return domain.progress.parts_field or domain.progress.total_field


async def fetch_outline_value(
    domain: Domain,
    identifiers: Mapping[str, str],
    primary: tuple[str, str] | None,
    providers: Mapping[str, Any],
) -> Any:
    """The outline field's value from the first provider that has one.

    Asked in the domain's declared enrichment order, by each identity kind the item
    carries, then the primary source by its own id. A provider that answers without
    the field, or says it has no such record, is an answer; if every one of them
    failed to answer at all, that is the provider's failure (502) rather than the
    record's (422).
    """
    field = outline_field(domain)
    if field is None:
        raise LibraryError(
            "outline_unavailable",
            f"{domain.label} entries have nothing to tick off",
            status_code=422,
        )
    attempts: list[Callable[[], Awaitable[Any]]] = []
    if domain.enrichment is not None:
        for provider_name in domain.enrichment.provider_order:
            provider = providers.get(provider_name)
            if provider is None or not hasattr(provider, "fetch_by_identifier"):
                continue
            for kind in domain.enrichment.identity_kinds:
                if identifiers.get(kind):
                    attempts.append(partial(provider.fetch_by_identifier, kind, identifiers[kind]))
    answered = False
    failed = False
    for call in attempts:
        try:
            payload = await call()
        except ProviderPayloadError as error:
            if error.code == "record_not_found":
                answered = True
            else:
                failed = True
            continue
        except Exception:  # noqa: BLE001 - a network failure is a provider failure
            failed = True
            continue
        answered = True
        value = payload.metadata.get(field)
        if value not in (None, [], ""):
            return value
    if primary is not None and primary[0] in providers:
        try:
            payload = await providers[primary[0]].fetch(primary[1])
        except ProviderPayloadError as error:
            answered = answered or error.code == "record_not_found"
            failed = failed or error.code != "record_not_found"
        except Exception:  # noqa: BLE001
            failed = True
        else:
            answered = True
            value = payload.metadata.get(field)
            if value not in (None, [], ""):
                return value
    if failed and not answered:
        raise LibraryError("provider_failure", "Metadata could not be fetched", status_code=502)
    raise LibraryError(
        "outline_unavailable",
        f"No provider lists the {domain.progress.unit_label}s for this one"
        if domain.progress is not None
        else "Nothing to tick off",
        status_code=422,
    )
