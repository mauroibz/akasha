from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import Engine

from book_tracker.application.library import LibraryError, LibraryService
from book_tracker.domain.identity import Identifier, InvalidIdentifier, normalize_identifier
from book_tracker.domain.providers import ItemPayload, Provider, SourceRef
from book_tracker.infrastructure.covers import CoverError, install_cover, prepare_cover
from book_tracker.infrastructure.repositories import (
    DomainRepository,
    IdentityConflict,
    SourceIdentity,
)


class AddService:
    def __init__(
        self,
        engine: Engine,
        providers: Mapping[str, Provider],
        *,
        cover_client: httpx.AsyncClient | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.repository = DomainRepository(engine)
        self.library = LibraryService(engine)
        self.providers = providers
        self.cover_client = cover_client
        self.data_dir = data_dir

    @staticmethod
    def _identifiers(values: Mapping[str, str]) -> list[Identifier]:
        identifiers: list[Identifier] = []
        for kind, value in values.items():
            try:
                identifiers.append(normalize_identifier(kind, value))
            except InvalidIdentifier as error:
                raise LibraryError("invalid_identifier", str(error), status_code=422) from error
        return identifiers

    async def _provider_payload(
        self, source: str, source_id: str, supplied_refs: Sequence[SourceRef]
    ) -> ItemPayload:
        provider = self.providers.get(source)
        if provider is None:
            raise LibraryError(
                "provider_disabled", "Metadata provider is not enabled", status_code=422
            )
        try:
            payload = await provider.fetch(source_id)
        except Exception as error:
            raise LibraryError(
                "provider_failure", "Metadata could not be fetched", status_code=502
            ) from error
        refs = list(payload.source_refs)
        primary_isbn = next(iter(self._identifiers(payload.identifiers)), None)
        for ref in supplied_refs:
            secondary = self.providers.get(ref.source)
            if secondary is None or ref in refs:
                continue
            try:
                candidate = await secondary.fetch(ref.source_id)
                secondary_isbn = next(iter(self._identifiers(candidate.identifiers)), None)
            except (Exception, LibraryError):
                continue
            if (
                primary_isbn
                and secondary_isbn
                and primary_isbn.normalized_value == secondary_isbn.normalized_value
            ):
                refs.append(ref)
        return ItemPayload(**{**payload.__dict__, "source_refs": tuple(refs)})

    async def add(
        self,
        *,
        manual: Mapping[str, Any] | None,
        source: str | None,
        source_id: str | None,
        supplied_refs: Sequence[SourceRef],
        status: str,
        score: int | None,
        shelf_ids: Sequence[int],
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        if manual is not None:
            cover_url = None
            title = str(manual["title"]).strip()
            authors = tuple(
                str(value).strip() for value in manual.get("authors", []) if str(value).strip()
            )
            metadata = {
                "authors": list(authors),
                **{key: manual[key] for key in ("publisher", "language") if manual.get(key)},
            }
            identifiers = self._identifiers(
                {"isbn": str(manual["isbn"])} if manual.get("isbn") else {}
            )
            sources = [SourceIdentity("manual", idempotency_key, True)] if idempotency_key else []
            subtitle = str(manual["subtitle"]) if manual.get("subtitle") else None
            year = int(manual["year"]) if manual.get("year") is not None else None
        else:
            assert source is not None and source_id is not None
            payload = await self._provider_payload(source, source_id, supplied_refs)
            cover_url = payload.cover_url
            title = payload.title
            subtitle = payload.subtitle
            authors = payload.authors
            year = payload.year
            metadata = {**payload.metadata, "authors": list(authors)}
            if payload.language:
                metadata["language"] = payload.language
            identifiers = self._identifiers(payload.identifiers)
            sources = [
                SourceIdentity(ref.source, ref.source_id, ref.source == payload.source)
                for ref in payload.source_refs
            ]
        prepared_cover: Path | None = None
        if cover_url and self.cover_client is not None and self.data_dir is not None:
            try:
                prepared_cover = await prepare_cover(self.cover_client, cover_url, self.data_dir)
            except CoverError:
                prepared_cover = None
        near_matches = self.repository.near_entry_ids(title, authors[0] if authors else "")
        try:
            result = self.repository.create_cached_entry(
                title=title,
                subtitle=subtitle,
                year=year,
                metadata=metadata,
                identifiers=identifiers,
                sources=sources,
                status=status,
                score=score,
                shelf_ids=shelf_ids,
            )
        except IdentityConflict as error:
            raise LibraryError(
                "identity_conflict", "Exact identities refer to different items"
            ) from error
        except LookupError as error:
            raise LibraryError(
                "shelf_not_found", "One or more shelves were not found", status_code=404
            ) from error
        if prepared_cover is not None:
            if result.already_exists or self.data_dir is None:
                prepared_cover.unlink(missing_ok=True)
            else:
                target: Path | None = None
                try:
                    target = install_cover(prepared_cover, self.data_dir, result.item_id)
                    self.repository.set_cover_path(result.item_id, f"covers/{result.item_id}.jpg")
                except (CoverError, LookupError):
                    if target is not None:
                        target.unlink(missing_ok=True)
        return {
            "entry": self.library.get_entry(result.entry_id),
            "already_exists": result.already_exists,
            "near_matches": [] if result.already_exists else near_matches,
        }
