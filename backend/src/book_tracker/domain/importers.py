"""The per-domain import boundary.

Readers turn an external source into one neutral record shape.  The shared import
service owns staging, validation, matching orchestration, the durable ledger, commit,
triage and undo; a connector owns only how its source is read and which identities it
trusts.  This is the import analogue of :mod:`book_tracker.domain.providers`.
"""

import fnmatch
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


#: The only multi-segment wildcard a member pattern may use, and only as its first
#: segment: "this name at any depth below the root".
MEMBER_WILDCARD = "**"


@dataclass(frozen=True)
class ImportInputSpec:
    """How the generic import screen asks for this connector's source.

    Everything past `help` is guidance the connector publishes about itself, so the
    shared screen renders a declaration rather than a branch on which connector it is
    holding. A `guide` is **ordered steps, not prose**: plain strings a list renders,
    which keeps the screen free of a markdown renderer and keeps a connector from
    shipping arbitrary markup into it (DEC-080).
    """

    kind: Literal["upload", "path", "directory"]
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
    #: Whether the connector can say, before an upload, which members are worth
    #: sending. See `IncrementalImporter`. A source with no durable identity should
    #: leave this false rather than guess (DEC-082).
    incremental: bool = False
    #: Whether this connector's `read` can take `ImportSource.files`. Required by
    #: `kind="directory"`, which would otherwise accept an upload it cannot use.
    accepts_files: bool = False
    #: A second way into the same connector, rendered beneath the primary on the same
    #: tab. Exactly one level deep: an alternate may not carry its own (DEC-081). It
    #: exists because a Calibre library is one source you may reach two ways — the
    #: folder on your machine, or a mount the server can already see — and splitting
    #: that across two tabs would name one thing twice.
    alternate: "ImportInputSpec | None" = None
    #: What this input will accept, when the shared route's defaults are the wrong
    #: size. `None` means the shared default. A folder of covers is legitimately far
    #: larger than a CSV, and raising the global ceiling for every connector to suit
    #: one of them is how a limit stops meaning anything.
    max_bytes: int | None = None
    max_files: int | None = None
    #: What a bundle from this input may contain, as anchored glob patterns over the
    #: relative path of each member: `"metadata.db"` is that file at the root and
    #: nothing else, `"**/cover.jpg"` is that name at any depth below the root. `**`
    #: is only meaningful as the first segment. Required by `kind="directory"`,
    #: because the shared route has to refuse a member before it writes a byte and
    #: only the connector knows what its source is shaped like.
    members: tuple[str, ...] = ()


def valid_member_pattern(pattern: str) -> bool:
    """Whether a connector's declared bundle member is a pattern this can match.

    Deliberately strict, because a pattern that never matches looks exactly like a
    connector refusing its own files. A segment may glob, `**` may lead and nothing
    else, and nothing may point outside the source root — a declaration is not a
    place to discover that traversal was possible.
    """
    if not pattern or pattern != pattern.strip() or pattern.startswith("/"):
        return False
    segments = pattern.split("/")
    if not all(segments) or any(part in ("..", ".") or part.startswith(".") for part in segments):
        return False
    if MEMBER_WILDCARD in segments[1:]:
        return False
    return segments != [MEMBER_WILDCARD]


def member_allowed(parts: Sequence[str], members: Sequence[str]) -> bool:
    """Whether a member's relative path is one this input declared it may contain.

    Anchored at the root, unlike `PurePosixPath.match`, which matches from the right
    and would let `anywhere/metadata.db` pass a declaration of `metadata.db`.
    """
    for pattern in members:
        segments = pattern.split("/")
        if segments[0] == MEMBER_WILDCARD:
            tail = segments[1:]
            if len(parts) > len(tail) and all(
                fnmatch.fnmatchcase(part, want)
                for part, want in zip(parts[-len(tail) :], tail, strict=True)
            ):
                return True
        elif len(parts) == len(segments) and all(
            fnmatch.fnmatchcase(part, want) for part, want in zip(parts, segments, strict=True)
        ):
            return True
    return False


@dataclass(frozen=True)
class ImportCandidate:
    """One file the client is offering to upload, named and measured but unread.

    `size` comes from the browser's own file metadata, so building a manifest costs
    no reads and no hashing — which matters because `crypto.subtle` is unavailable on
    the plain-HTTP LAN origin this application is served from (DEC-082).
    """

    path: str
    size: int


@dataclass(frozen=True)
class ImportPlan:
    """Which of the offered candidates are actually worth sending.

    `holding` is how many the library already has, so the screen can say what it is
    skipping rather than silently sending less than the reader chose.
    """

    wanted: tuple[str, ...]
    holding: int = 0
    reason: str | None = None


class ImportInventory(Protocol):
    """The narrow library view a planning connector may consult.

    Three questions, batched, and nothing else — the same containment `ImportMatcher`
    established. They are kept apart because they have different answers: "do you have
    this?", "does it have a picture?" and "which files does it already hold?" would,
    conflated, skip a cover for an item that never got one or a file for an item that
    only ever got a cover.
    """

    def existing(self, kind: str, values: Sequence[str]) -> frozenset[str]: ...

    def with_cover(self, kind: str, values: Sequence[str]) -> frozenset[str]: ...

    def attached(self, kind: str, values: Sequence[str]) -> Mapping[str, frozenset[str]]:
        """For each identity value, the attachment filenames its item already holds."""
        ...


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
    """One source submitted through the generic route.

    Exactly one of `data`, `path` or `directory` is set, matching the input's `kind`.

    `directory` is a **materialized bundle**: the route has already streamed each
    uploaded member to disk under `<directory>/library/<relative path>`, having refused
    anything absolute, anything containing `..`, anything with a hidden segment, and
    anything the connector did not ask for. It is a directory rather than a mapping of
    bytes on purpose — a folder of covers is far larger than any single file in it, and
    holding the whole bundle in memory to hand it over would put the peak at the size of
    the library instead of the size of one cover. The route owns its lifetime and
    removes it once preview has staged what it needs.
    """

    data: bytes | None = None
    filename: str | None = None
    path: str | None = None
    directory: Path | None = None
    #: The client's offer, as raw JSON, when this source came through the plan route.
    manifest: str | None = None


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
    #: The files that belong to this record, by relative path under the source root.
    #: A connector declares them at read time so a shared route can resolve an
    #: uploaded path back to the record it belongs to without knowing what any
    #: particular source looks like on disk.
    source_files: tuple[str, ...] = ()


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
    """The narrow library view an importer's matching strategy may use.

    `year` and `item_type` were added for a source that carries no creator at all. A
    Letterboxd export names a film by title and year, and the film it means may already
    be in the library under a Wikidata slug rather than the export's short URI — so
    title plus **exact** year may be offered as an ambiguity, never as a match.

    `item_type` scopes that offer, and exists because title plus year is a far weaker
    signal than title plus author: a novel and the film made of it routinely share both.
    An importer that passes neither behaves exactly as it did before (technical spec 6.1).
    """

    def match(
        self,
        *,
        identifiers: Sequence[Identifier],
        title: str,
        first_author: str,
        year: int | None = None,
        item_type: str | None = None,
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


@runtime_checkable
class IncrementalImporter(Protocol):
    """A connector that can say what is worth uploading before it is uploaded.

    Separate from `Importer` for the reason `BrowsableImporter` is: most sources have
    nothing to plan. The connector is handed the cheap half of the source — for a
    Calibre bundle, `metadata.db` alone — plus what the client is offering, and answers
    with the subset it wants.
    """

    def plan(
        self,
        source: ImportSource,
        candidates: Sequence[ImportCandidate],
        inventory: ImportInventory,
        context: ImportReadContext,
    ) -> ImportPlan: ...


def planned_upload(candidates: Sequence[ImportCandidate], plan: ImportPlan) -> ImportPlan:
    """The plan as the boundary may publish it.

    A connector may decline a candidate; it may not invent one. Naming a path the
    client never offered would have the client upload something it did not choose,
    which is the client's business and not the connector's.
    """
    offered = {candidate.path for candidate in candidates}
    for path in plan.wanted:
        if path not in offered:
            raise ValueError(f"planned path {path!r} was not offered as a candidate")
    return plan
