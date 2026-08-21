"""The per-domain import boundary.

Readers turn an external source into one neutral record shape.  The shared import
service owns staging, validation, matching orchestration, the durable ledger, commit,
triage and undo; a connector owns only how its source is read and which identities it
trusts.  This is the import analogue of :mod:`book_tracker.domain.providers`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from book_tracker.domain.identity import Identifier
from book_tracker.domain.matching import MatchDecision


class ImportReadError(ValueError):
    """A source a registered reader cannot safely normalize."""

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True)
class ImportInputSpec:
    """How the generic import screen asks for this connector's source."""

    kind: Literal["upload", "path"]
    label: str
    field: str
    accept: str | None = None
    placeholder: str | None = None
    help: str | None = None


@dataclass(frozen=True)
class ImportSource:
    """One source submitted through the generic route."""

    data: bytes | None = None
    filename: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class ImportReadContext:
    """Host paths a reader may consult without learning about the application."""

    path_root: Path


@dataclass(frozen=True)
class ImportItem:
    """The domain-neutral item half of a normalized import row."""

    title: str
    subtitle: str | None
    year: int | None
    identifiers: Mapping[str, str]
    metadata: Mapping[str, Any]
    creator_sort: str | None = None


@dataclass(frozen=True)
class ImportEntry:
    """The personal half of a normalized row.

    `values` is for the passage fields declared by the target domain.  Score, notes,
    arrival time and triage suggestions are neutral entry concepts and stay explicit.
    """

    score: int | None
    notes: str | None
    date_added: str | None
    values: Mapping[str, Any]
    score_provisional: bool = False
    suggested_status: str | None = None


@dataclass(frozen=True)
class NormalizedImportRecord:
    """One reader row after source vocabulary has stopped leaking upward."""

    row_number: int
    item: ImportItem
    entry: ImportEntry
    shelves: tuple[str, ...]
    errors: tuple[Mapping[str, Any], ...]
    source_fields: Mapping[str, Any]
    cover_source: str | None = None
    cover_stage: str | None = None


@dataclass(frozen=True)
class ImportSnapshot:
    """A stable reader result; commit never re-opens the source."""

    fingerprint: str
    filename: str
    source_descriptor: Mapping[str, Any]
    records: tuple[NormalizedImportRecord, ...]
    archive_name: str | None = None
    archive_data: bytes | None = None


class ImportMatcher(Protocol):
    """The narrow library view an importer's matching strategy may use."""

    def match(
        self,
        *,
        identifiers: Sequence[Identifier],
        title: str,
        first_author: str,
    ) -> MatchDecision: ...


@runtime_checkable
class Importer(Protocol):
    """A connector registered by the domain it targets.

    The declaration is intentionally small but explicit about the four choices that
    make a connector portable: its reader, matching strategy, authoritative identity
    kinds and target domain.  `stage` copies any source/assets only after fingerprint
    replay has been checked, so a duplicate preview leaves no orphan directory.
    """

    name: str
    label: str
    item_type: str
    input: ImportInputSpec
    identity_kinds: frozenset[str]

    def read(self, source: ImportSource, context: ImportReadContext) -> ImportSnapshot: ...

    def stage(
        self, snapshot: ImportSnapshot, directory: Path, data_dir: Path
    ) -> ImportSnapshot: ...

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision: ...
