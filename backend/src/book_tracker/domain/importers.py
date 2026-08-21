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
    """A source a registered reader cannot safely normalize.

    `code` is for the client to branch on and belongs to the connector's declared
    `error_codes`; `message` is for the log. `user_message` and `action` are what a
    person reads: the second is one imperative sentence naming the thing to do next
    ("Close Calibre and try again"), because a failure a reader cannot act on is a
    dead end no matter how precisely it is described (DEC-080).
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
        *,
        user_message: str | None = None,
        action: str | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        self.user_message = user_message
        self.action = action
        super().__init__(message)


@dataclass(frozen=True)
class ImportInputSpec:
    """How the generic import screen asks for this connector's source.

    Everything past `help` is guidance the connector publishes about itself, so the
    shared screen renders a declaration rather than a branch on which connector it is
    holding. A `guide` is **ordered steps, not prose**: plain strings a list renders,
    which keeps the screen free of a markdown renderer and keeps a connector from
    shipping arbitrary markup into it (DEC-080).
    """

    kind: Literal["upload", "path"]
    label: str
    field: str
    accept: str | None = None
    placeholder: str | None = None
    help: str | None = None
    #: How to obtain the source, one step per string, rendered in order.
    guide: tuple[str, ...] = ()
    #: What the input says while nothing has been chosen.
    empty_state: str | None = None
    #: Where the source's own documentation lives. https, or absent.
    help_url: str | None = None
    #: Whether the connector can list what a `path` source holds. See `BrowsableImporter`.
    browsable: bool = False


@dataclass(frozen=True)
class ImportBrowseResult:
    """One level of a `path` connector's source, named relatively and nothing more.

    `directories` are bare names, never absolute paths: the mount's layout on the host
    is not the reader's business and publishing it would leak the deployment's shape to
    anyone who can reach the LAN. `importable` is the connector's own answer to "is this
    folder a source I could read?", which is what lets the picker offer Preview on the
    right folder instead of making the reader guess.
    """

    path: str
    parent: str | None
    directories: tuple[str, ...]
    importable: bool


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
    #: Every code this connector's reader may raise. Closed, so a screen can decide
    #: what to say about a failure and an unknown code cannot leave the boundary.
    error_codes: frozenset[str]

    def read(self, source: ImportSource, context: ImportReadContext) -> ImportSnapshot: ...

    def stage(
        self, snapshot: ImportSnapshot, directory: Path, data_dir: Path
    ) -> ImportSnapshot: ...

    def match(self, record: NormalizedImportRecord, matcher: ImportMatcher) -> MatchDecision: ...


@runtime_checkable
class BrowsableImporter(Protocol):
    """A connector whose source is a place, and which can say what that place holds.

    Separate from `Importer` on purpose: an upload has nothing to browse, and folding
    this into the main protocol would make every future connector implement a method it
    has no use for. A connector opts in by setting `input.browsable` and implementing
    this; the conformance suite refuses one that declares the first without the second.
    """

    def browse(self, path: str, context: ImportReadContext) -> ImportBrowseResult: ...


def declared_read_error(importer: Importer, error: ImportReadError) -> ImportReadError:
    """The error as the boundary may publish it.

    A connector that raises a code outside its declaration is a defect in the connector,
    and no screen has copy for the code it invented. Rather than leak an unknown
    vocabulary to the client, republish it under one stable code and keep everything a
    reader can act on.
    """
    if error.code in importer.error_codes:
        return error
    return ImportReadError(
        "undeclared_import_error",
        f"{importer.label} raised an undeclared error code {error.code!r}: {error}",
        dict(error.details),
        user_message=error.user_message,
        action=error.action,
    )
