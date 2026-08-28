"""Every domain, held to the same contract.

A third domain passes this suite **by existing**: every check is parametrized over
`DOMAINS`, so nothing here is extended when one is added. That is the whole point.
Sprint 025 proved a second domain was affordable by building one; this is what stops
the third from being built by reading how the second was built.

The checks are functions rather than test bodies, because the same code has to run two
ways: over the domains this build registers, and over deliberately broken ones declared
at the bottom of this file. **A conformance suite that cannot fail is decoration**, and
the malformed fixtures are what keep this one honest.

They come in two groups, and the split is the finding of Sprint 028's measurement:

- `REGISTRY_CHECKS` are what a domain satisfies **on its own** — internal consistency of
  its vocabularies, its fields, its identity rule and its URL recognizer. `A_THIRD_DOMAIN`
  below satisfies every one of them without being registered anywhere.
- `CORE_CHECKS` are whether the core **can host** this domain — whether the published
  unions carry its values and whether the database will accept them. Books and albums
  pass. `A_THIRD_DOMAIN` fails both, and that failure is the measurement: a domain is not
  yet a unit of code, because declaring one is not enough to make the core accept it.
"""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from book_tracker.application.providers import resolve_input
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.importers import (
    BrowsableImporter,
    ImportCandidate,
    Importer,
    ImportInputSpec,
    ImportPlan,
    ImportReadError,
    IncrementalImporter,
    declared_read_error,
    planned_upload,
    valid_member_pattern,
)
from book_tracker.domain.providers import (
    EnrichingProvider,
    IdentityStrategy,
    ItemPayload,
    SearchCandidate,
)
from book_tracker.domain.registry import (
    ALL_STATUSES,
    DOMAINS,
    IMPORTERS,
    IMPORTERS_BY_DOMAIN,
    EntryFormat,
    EntryStatus,
    ItemTypeName,
)
from book_tracker.domain.spec import (
    PASSAGE_FIELDS,
    RESERVED_FIELD_NAMES,
    Domain,
    EnrichmentSpec,
    FieldSpec,
    FormatSpec,
    ProgressSpec,
    StatusSpec,
    UrlMatch,
)
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app
from book_tracker.migrations import upgrade

RegistryCheck = Callable[[Domain], None]
CoreCheck = Callable[[Domain, Engine], None]
AppCheck = Callable[[Domain, FastAPI], None]

REGISTRY_CHECKS: dict[str, RegistryCheck] = {}
CORE_CHECKS: dict[str, CoreCheck] = {}
APP_CHECKS: dict[str, AppCheck] = {}


def assert_importer_contract(importer: object) -> None:
    """An importer is complete enough for the generic pipeline to host it."""
    assert isinstance(importer, Importer)
    assert importer.name and importer.name.isidentifier() and importer.name.islower()
    assert importer.label
    assert importer.item_type in DOMAINS
    assert isinstance(importer.input, ImportInputSpec)
    assert importer.input.field and importer.input.field.isidentifier()
    assert importer.identity_kinds, f"{importer.name} declares no authoritative identity kinds"
    assert all(kind for kind in importer.identity_kinds)
    assert callable(importer.read), f"{importer.name} declares no reader"
    assert callable(importer.stage), f"{importer.name} declares no staging strategy"
    assert callable(importer.match), f"{importer.name} declares no match strategy"
    assert_declared_guidance(importer)


def assert_declared_guidance(importer: Importer) -> None:
    """What a connector publishes about itself is well formed.

    The point of these fields is that a connector guides its own users without
    anybody editing the shared import screen (DEC-080). That only holds if the
    screen can render a declaration without inspecting which connector wrote it,
    so the shapes are checked here rather than trusted.
    """
    spec = importer.input
    assert isinstance(spec.guide, tuple), f"{importer.name} guide must be ordered steps"
    assert all(isinstance(step, str) and step.strip() for step in spec.guide), (
        f"{importer.name} guide has an empty step"
    )
    assert spec.empty_state is None or spec.empty_state.strip()
    assert spec.help_url is None or spec.help_url.startswith("https://"), (
        f"{importer.name} help_url is not an https address"
    )
    assert not spec.browsable or spec.kind == "path", (
        f"{importer.name} offers browsing for a source that is not a place"
    )
    assert not spec.browsable or isinstance(importer, BrowsableImporter), (
        f"{importer.name} declares browsing but has no browse method"
    )
    # Same shape as browsable: the flag is a promise the connector has to keep, and
    # a source with no durable identity should decline rather than guess (DEC-082).
    assert not spec.incremental or isinstance(importer, IncrementalImporter), (
        f"{importer.name} declares incremental but has no plan method"
    )
    assert_declared_envelope(importer, spec)
    if spec.alternate is not None:
        assert spec.alternate.alternate is None, (
            f"{importer.name} nests an alternate inside an alternate"
        )
        assert spec.alternate.field != spec.field, (
            f"{importer.name} gives its alternate the same field as its primary"
        )
        assert spec.alternate.field and spec.alternate.field.isidentifier()
        assert spec.alternate.label
        assert_declared_envelope(importer, spec.alternate)


def assert_declared_envelope(importer: Importer, spec: ImportInputSpec) -> None:
    """What this input will accept, when the shared default is the wrong size."""
    for name in ("max_bytes", "max_files"):
        cap = getattr(spec, name)
        assert cap is None or cap > 0, f"{importer.name} declares {name}={cap!r}"
    # A directory is a set of files, and a reader that cannot take one would accept
    # the upload and then find nothing it understands.
    assert spec.kind != "directory" or spec.accepts_files, (
        f"{importer.name} offers a directory its reader cannot read"
    )
    # The shared route has to refuse a member before it writes a byte, and only the
    # connector knows what its source is shaped like (DEC-083).
    assert spec.kind != "directory" or spec.members, (
        f"{importer.name} offers a directory without saying what it may contain"
    )
    assert all(valid_member_pattern(pattern) for pattern in spec.members), (
        f"{importer.name} declares a bundle member pattern that cannot be matched safely"
    )
    # The vocabulary is closed so a screen can decide what to say about a
    # failure, and so an undeclared code cannot reach a reader as itself.
    assert importer.error_codes, f"{importer.name} declares no error vocabulary"
    assert all(code and code.isidentifier() and code.islower() for code in importer.error_codes), (
        f"{importer.name} declares a malformed error code"
    )


def registry_check(function: RegistryCheck) -> RegistryCheck:
    REGISTRY_CHECKS[function.__name__] = function
    return function


def core_check(function: CoreCheck) -> CoreCheck:
    CORE_CHECKS[function.__name__] = function
    return function


def app_check(function: AppCheck) -> AppCheck:
    APP_CHECKS[function.__name__] = function
    return function


# --------------------------------------------------------------------------------------
# What a domain must satisfy on its own
# --------------------------------------------------------------------------------------


@registry_check
def the_domain_names_itself(domain: Domain) -> None:
    """`item_type` is stored in `items.type` and is permanent; `label` is copy."""
    assert domain.item_type, "a domain must declare an item_type"
    assert domain.item_type.isidentifier() and domain.item_type.islower(), (
        f"{domain.item_type!r} is stored in every row and appears in query strings, "
        "so it must be a lowercase identifier"
    )
    assert domain.label, f"{domain.item_type} declares no label"
    # "Your reading data" over a record is a book's phrase (DEC-057). A domain that
    # forgets this inherits the wrong one silently, so it is required rather than
    # defaulted-and-hoped.
    assert domain.entry_panel_label, f"{domain.item_type} declares no entry panel label"


@registry_check
def statuses_are_a_usable_vocabulary(domain: Domain) -> None:
    """Seam 5b: the shared layer knows only that statuses exist and one is the inbox."""
    values = [status.value for status in domain.statuses]
    assert values, f"{domain.item_type} declares no statuses"
    assert len(values) == len(set(values)), f"{domain.item_type} repeats a status"
    # Imports land in the inbox whatever the domain, and the default library view hides
    # it — so it exists everywhere and is never offered as something to choose.
    assert "unsorted" in values, f"{domain.item_type} has no inbox to import into"
    assert not domain.status("unsorted").choosable, (  # type: ignore[union-attr]
        f"{domain.item_type} offers 'unsorted' as a choice"
    )
    assert domain.default_status in values, (
        f"{domain.item_type} defaults to {domain.default_status!r}, which it does not declare"
    )
    assert all(status.label for status in domain.statuses), f"{domain.item_type} has a bare status"
    keys = [status.hotkey for status in domain.statuses if status.hotkey]
    assert len(keys) == len(set(keys)), f"{domain.item_type} binds one triage key twice"
    assert all(status.hotkey for status in domain.statuses if status.choosable), (
        f"{domain.item_type} has a choosable status with no triage key"
    )


@registry_check
def formats_are_a_usable_vocabulary(domain: Domain) -> None:
    """DEC-059: the vocabulary is closed and declared, which is what a shelf is not."""
    values = [row.value for row in domain.formats]
    assert values, f"{domain.item_type} declares no formats"
    assert len(values) == len(set(values)), f"{domain.item_type} repeats a format"
    assert all(row.label for row in domain.formats), f"{domain.item_type} has a bare format"


@registry_check
def entry_fields_are_passage_fields(domain: Domain) -> None:
    """DEC-057: a domain declares which of the three it has, and may not invent a fourth.

    An unknown name here would be silently ignored by `validate_entry_fields`, which
    refuses *absent* names — so the domain would believe it had a field nothing writes.
    """
    unknown = domain.entry_fields - PASSAGE_FIELDS
    assert not unknown, f"{domain.item_type} declares entry fields that do not exist: {unknown}"


@registry_check
def entry_field_labels_name_fields_this_domain_has(domain: Domain) -> None:
    """A domain may rename a passage field it has, and only one it has.

    `entry_panel_label` made the heading the domain's copy and left the fields under it
    reading `Rereads` on everything. These are the same kind of copy. A label for a
    field the domain does not declare is a label nothing will ever render, which looks
    exactly like a label that is not working.
    """
    unknown = set(domain.entry_field_labels) - domain.entry_fields
    assert not unknown, f"{domain.item_type} labels entry fields it does not declare: {unknown}"
    assert all(label and label.strip() for label in domain.entry_field_labels.values()), (
        f"{domain.item_type} has a bare entry field label"
    )


@registry_check
def progress_counts_something_this_domain_declares(domain: Domain) -> None:
    """DEC-077 shape (a): a count the domain means something by, and can render.

    `None` is the complete answer for a book — a page count is not something the entry
    records. What is checked for a domain that does declare one is that it can be
    *rendered*: a label and a unit to put beside the number, and a `total_field` that
    names a real numeric field when it names anything at all.

    That last check is the same trap Sprint 039 found in `completeness_fields`: a name
    the domain never stores is always absent, so a total pointing at nothing would make
    "20 / —" the permanent reading rather than an occasional one.
    """
    spec = domain.progress
    if spec is None:
        return
    assert spec.label and spec.label.strip(), f"{domain.item_type} progress has no label"
    assert spec.unit_label and spec.unit_label.strip(), (
        f"{domain.item_type} progress has no unit to count in"
    )
    if spec.total_field is None:
        return
    field = next((row for row in domain.fields if row.name == spec.total_field), None)
    assert field is not None, (
        f"{domain.item_type} counts progress towards {spec.total_field!r}, "
        "which it does not declare as a metadata field"
    )
    assert field.type == "number", (
        f"{domain.item_type} counts progress towards {spec.total_field!r}, "
        f"which is {field.type} rather than a number"
    )


@registry_check
def enrichment_is_answerable_by_this_domain(domain: Domain) -> None:
    """DEC-067 row 3: what a domain enriches on, and what counts as still incomplete.

    `None` is a complete answer — an album's one release fetch already returns
    everything it has. What is checked is that a domain which *does* declare
    enrichment declares something the backfill can act on. The
    `completeness_fields` rule is the sharp one: a name this domain does not
    declare is always absent from its metadata, so the record would look
    incomplete for ever and be re-queued on every backfill. That is exactly what
    would have happened to anime under the old rule, which named books' fields
    for every domain.
    """
    spec = domain.enrichment
    if spec is None:
        return
    assert spec.identity_kind and spec.identity_kind.strip(), (
        f"{domain.item_type} enriches on an unnamed identifier kind"
    )
    assert spec.provider_order, f"{domain.item_type} enriches but names no provider to ask"
    assert all(name and name.strip() for name in spec.provider_order), (
        f"{domain.item_type} names a blank provider"
    )
    assert len(set(spec.provider_order)) == len(spec.provider_order), (
        f"{domain.item_type} names one provider twice in its enrichment order"
    )
    assert spec.completeness_fields, (
        f"{domain.item_type} enriches but nothing would ever make a record complete"
    )
    declared = {field.name for field in domain.fields}
    unknown = set(spec.completeness_fields) - declared
    assert not unknown, (
        f"{domain.item_type} judges completeness by fields it does not declare: "
        f"{unknown}. A field this domain never stores is always absent, so every "
        "record would be re-queued for ever."
    )


@registry_check
def fields_are_described_completely(domain: Domain) -> None:
    """Seam 3: storage is opaque, so the spec is the only description there is."""
    names = [field.name for field in domain.fields]
    assert names, f"{domain.item_type} declares no metadata fields"
    assert len(names) == len(set(names)), f"{domain.item_type} declares one field twice"
    shadowed = set(names) & RESERVED_FIELD_NAMES
    assert not shadowed, (
        f"{domain.item_type} metadata shadows the neutral item columns {shadowed}; "
        "those belong to every domain and are edited beside the metadata, not inside it"
    )
    for field in domain.fields:
        assert field.label, f"{domain.item_type}.{field.name} has no label"
        if field.type == "rows":
            assert field.columns, f"{domain.item_type}.{field.name} is rows with no columns"
            column_names = [column.name for column in field.columns]
            assert len(column_names) == len(set(column_names)), (
                f"{domain.item_type}.{field.name} declares one column twice"
            )
            assert all(column.label for column in field.columns), (
                f"{domain.item_type}.{field.name} has a bare column"
            )
        else:
            assert not field.columns, (
                f"{domain.item_type}.{field.name} is {field.type} and carries columns; "
                "only a rows field has them, and the renderer keys on that"
            )
        if field.minimum is not None and field.maximum is not None:
            assert field.minimum <= field.maximum, (
                f"{domain.item_type}.{field.name} admits no value at all"
            )


@registry_check
def the_cover_chooser_is_only_declared_where_it_can_work(domain: Domain) -> None:
    """DEC-067 row 7 chose to declare the capability, not to generalise the mechanism.

    The shared chooser is Open Library's work-editions path, so a domain may only
    declare `chooses_covers` if Open Library is one of the sources it prefers. Anything
    else offers the reader a control that can only say no — which is what an album did
    from Sprint 025 until this sprint. A domain with its own cover-candidate source is
    the point at which the mechanism becomes per-domain rather than the declaration.
    """
    if not domain.chooses_covers:
        return
    assert "openlibrary" in domain.identity.source_preference, (
        f"{domain.item_type} declares it chooses covers, but the shared chooser is "
        "Open Library's work-editions path and this domain does not prefer that source"
    )


@registry_check
def identity_is_a_strategy(domain: Domain) -> None:
    """Seam 2: how two candidates are judged the same record, and who wins a merge.

    `None` from `identity_key` means *never merge*, which is albums' complete answer
    (DEC-052) — so what is checked is that the rule answers, not that it groups.
    """
    identity = domain.identity
    assert isinstance(identity, IdentityStrategy)
    assert identity.source_preference, (
        f"{domain.item_type} names no source preference, so nothing decides which "
        "provider's row wins a merge or breaks a ranking tie"
    )
    assert all(name for name in identity.source_preference)
    bare = SearchCandidate(
        source=identity.source_preference[0],
        source_id="conformance",
        source_refs=(),
        title="",
        subtitle=None,
        creators=(),
        year=None,
        cover_url=None,
        identifiers={},
        language=None,
        metadata={},
    )
    key = identity.identity_key(bare)
    assert key is None or isinstance(key, str), (
        f"{domain.item_type} identity_key answered {key!r}; it must be a string or None"
    )


@registry_check
def the_recognizer_answers_for_any_string(domain: Domain) -> None:
    """Seam 6, and the one check that is about *other* domains.

    `resolve_input` asks every registered domain in turn what a pasted string means.
    A recognizer that raises therefore does not fail its own domain — it denies every
    domain after it in the registry its turn, and the reader gets a provider error for
    what is really a typo. One domain must not be able to break another's add box.
    """
    for probe in RECOGNIZER_PROBES:
        try:
            answer = domain.recognize(probe)
        except Exception as error:  # noqa: BLE001 - the point of the check
            raise AssertionError(
                f"{domain.item_type} raised {type(error).__name__} on {probe!r}; "
                "a recognizer answers or declines, it never raises"
            ) from error
        assert answer is None or isinstance(answer, UrlMatch), (
            f"{domain.item_type} answered {answer!r} for {probe!r}"
        )
        if answer is not None:
            assert answer.action in {"fetch", "work", "search"}
            assert answer.value, f"{domain.item_type} matched {probe!r} with nothing to spend"


RECOGNIZER_PROBES = (
    "",
    "   ",
    "x",
    "not a url at all",
    # Malformed enough that `urlsplit` itself raises: bracket-parsing for IPv6.
    "http://[",
    "http://[::1",
    "https://",
    "//",
    "https://example.invalid/nothing/here",
    "978-3-16-148410-0",
    "9780000000000",
    "https://openlibrary.org/books/OL1M",
    "https://openlibrary.org/works/OL1W",
    "https://musicbrainz.org/release-group/00000000-0000-0000-0000-000000000000",
    "https://books.google.com/books?id=zyTCAlFPjgYC",
    "https://anilist.co/anime/1/example",
    "https://kitsu.app/anime/example",
    "https://myanimelist.net/anime/1/example",
    "a" * 4000,
)


# --------------------------------------------------------------------------------------
# Whether the core can host this domain
# --------------------------------------------------------------------------------------


@core_check
def the_published_unions_carry_this_domain(domain: Domain, _engine: Engine) -> None:
    """The API surface. A value missing here is a value no client may ever send.

    The unions are spelled out rather than built from the registry, because a dynamic
    `StrEnum` is opaque to mypy and this is a public contract — so this assertion is the
    safety net that the construction is not.
    """
    published = {member.value for member in EntryStatus}
    missing = {status.value for status in domain.statuses} - published
    assert not missing, f"EntryStatus does not publish {domain.item_type}'s {missing}"
    formats = {member.value for member in EntryFormat}
    missing_formats = {row.value for row in domain.formats} - formats
    assert not missing_formats, (
        f"EntryFormat does not publish {domain.item_type}'s {missing_formats}"
    )
    assert domain.item_type in {member.value for member in ItemTypeName}, (
        f"ItemTypeName does not publish {domain.item_type!r}, "
        "so the library cannot be filtered to it"
    )


@core_check
def the_database_accepts_every_declared_status(domain: Domain, engine: Engine) -> None:
    """The check the measurement forced, and the reason `ck_entries_status` is gone.

    It was rendered from `ALL_STATUSES` **at migration-write time**
    (`0013_entry_formats.py`), so it was a frozen list rather than a live rule: a domain
    declaring a status books and albums lacked passed `validate_status` and was then
    refused by SQLite, which meant adding a domain required a migration on a shared
    table. Passing the API and failing the database is the worst possible split, because
    it fails at write time on the reader's data rather than at registration.

    Migration `0014_status_is_the_domains` dropped it (DEC-067 row 1). This check now
    holds the property that replaced it: whatever a domain declares, the database takes.
    """
    with engine.begin() as connection:
        item_id = connection.execute(
            text(
                "INSERT INTO items (type, title, metadata, created_at, updated_at) "
                "VALUES (:type, :title, '{}', :now, :now) RETURNING id"
            ),
            {"type": domain.item_type, "title": f"Conformance {domain.item_type}", "now": _NOW},
        ).scalar_one()
    for status in domain.statuses:
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO entries (user_id, item_id, status, date_added, "
                        "created_at, updated_at) VALUES (1, :item, :status, :now, :now, :now)"
                    ),
                    {"item": item_id, "status": status.value, "now": _NOW},
                )
                connection.execute(
                    text("DELETE FROM entries WHERE item_id=:item"), {"item": item_id}
                )
        except IntegrityError as error:
            raise AssertionError(
                f"the database refuses {domain.item_type}'s status {status.value!r}, "
                "so this domain cannot be added without a migration on the shared "
                "`entries` table"
            ) from error


# --------------------------------------------------------------------------------------
# Whether this built application actually wires what the domain names
# --------------------------------------------------------------------------------------


@app_check
def declared_providers_are_constructed_for_this_domain(domain: Domain, app: FastAPI) -> None:
    """Declarations must name adapters this build constructs for the same domain."""
    catalog = app.state.provider_catalog
    enrichment_names = set(domain.enrichment.provider_order) if domain.enrichment else set()
    names = set(domain.identity.source_preference) | enrichment_names
    for name in names:
        provider = catalog.get(name)
        assert provider is not None, (
            f"{domain.item_type} names {name!r}, which this build does not construct"
        )
        assert provider.item_type == domain.item_type, (
            f"{domain.item_type} names {name!r}, which serves {provider.item_type!r}"
        )
        if name in enrichment_names:
            assert isinstance(provider, EnrichingProvider), (
                f"{domain.item_type} enriches through {name!r}, which cannot answer "
                "background enrichment"
            )


@app_check
def recognized_provider_routes_are_constructed_for_this_domain(
    domain: Domain, app: FastAPI
) -> None:
    """Every concrete provider route the recognizer emits must be spendable."""
    catalog = app.state.provider_catalog
    for probe in RECOGNIZER_PROBES:
        match = domain.recognize(probe)
        if match is None or not match.provider:
            continue
        provider = catalog.get(match.provider)
        assert provider is not None, (
            f"{domain.item_type} recognizes {probe!r} through {match.provider!r}, "
            "which this build does not construct"
        )
        assert provider.item_type == domain.item_type, (
            f"{domain.item_type} routes {probe!r} to {match.provider!r}, which serves "
            f"{provider.item_type!r}"
        )


@app_check
def cover_choice_has_a_provider_that_can_offer_candidates(domain: Domain, app: FastAPI) -> None:
    """A published cover chooser must have a constructed candidate source."""
    if not domain.chooses_covers:
        return
    catalog = app.state.provider_catalog
    candidates = [
        catalog.get(name)
        for name in domain.identity.source_preference
        if catalog.get(name) is not None
    ]
    assert any(
        provider.item_type == domain.item_type and callable(getattr(provider, "resolve_work", None))
        for provider in candidates
    ), f"{domain.item_type} chooses covers but no constructed provider offers candidates"


_NOW = "2026-08-15T00:00:00Z"


@pytest.fixture(scope="module")
def migrated(tmp_path_factory: pytest.TempPathFactory) -> Engine:
    """One migrated database for the whole module: the schema is what is under test."""
    configured = Settings(
        data_dir=tmp_path_factory.mktemp("conformance"), user_agent_contact="test@example.invalid"
    )
    assert configured.database_url is not None
    upgrade(configured.database_url)
    return create_engine(configured)


# --------------------------------------------------------------------------------------
# The suite, run over the domains this build registers
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(REGISTRY_CHECKS))
@pytest.mark.parametrize("domain", list(DOMAINS.values()), ids=lambda row: str(row.item_type))
def test_a_registered_domain_satisfies_the_contract(name: str, domain: Domain) -> None:
    REGISTRY_CHECKS[name](domain)


@pytest.mark.parametrize("name", sorted(CORE_CHECKS))
@pytest.mark.parametrize("domain", list(DOMAINS.values()), ids=lambda row: str(row.item_type))
def test_the_core_can_host_a_registered_domain(name: str, domain: Domain, migrated: Engine) -> None:
    CORE_CHECKS[name](domain, migrated)


@pytest.mark.anyio
@pytest.mark.parametrize("name", sorted(APP_CHECKS))
async def test_the_built_application_wires_a_registered_domain(name: str, tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        for domain in DOMAINS.values():
            APP_CHECKS[name](domain, app)


@pytest.mark.parametrize("importer", list(IMPORTERS.values()), ids=lambda row: str(row.name))
def test_a_registered_importer_satisfies_the_contract(importer: object) -> None:
    """A connector is held to the import contract merely by being registered."""
    assert_importer_contract(importer)


def test_importers_are_registered_under_the_domain_they_target() -> None:
    registered = {
        importer.name: item_type
        for item_type, importers in IMPORTERS_BY_DOMAIN.items()
        for importer in importers
    }
    assert registered == {name: importer.item_type for name, importer in IMPORTERS.items()}
    assert {importer.name for importer in IMPORTERS_BY_DOMAIN["book"]} == {
        "goodreads",
        "calibre",
    }


def test_the_importer_suite_rejects_a_missing_contract_member() -> None:
    """The contract can fail: a connector with no match strategy is incomplete."""

    class MissingMatch:
        name = "missing"
        label = "Missing"
        item_type = "book"
        input = ImportInputSpec(kind="upload", label="File", field="file")
        identity_kinds = frozenset({"isbn"})

        def read(self) -> None:
            return None

    with pytest.raises(AssertionError):
        assert_importer_contract(MissingMatch())


class _DeclaringImporter:
    """A well-formed declaration, used as the control for the malformed ones."""

    name = "declaring"
    label = "Declaring"
    item_type = "book"
    input = ImportInputSpec(
        kind="upload",
        label="File",
        field="file",
        guide=("Open the export page.", "Download the file."),
        empty_state="Drop the export here.",
        help_url="https://example.invalid/export",
    )
    identity_kinds = frozenset({"isbn"})
    error_codes = frozenset({"invalid_source"})

    def read(self, *_args: object) -> None:
        return None

    def stage(self, *_args: object) -> None:
        return None

    def match(self, *_args: object) -> None:
        return None


def test_a_well_formed_declaration_passes() -> None:
    assert_declared_guidance(_DeclaringImporter())


def test_a_connector_may_declare_a_second_way_in() -> None:
    """One connector, two affordances, one tab (DEC-081)."""

    class TwoWays(_DeclaringImporter):
        input = replace(
            _DeclaringImporter.input,
            alternate=ImportInputSpec(kind="path", label="Path", field="library_path"),
        )

    assert_declared_guidance(TwoWays())


@pytest.mark.parametrize(
    ("name", "alternate"),
    [
        # Depth is exactly one. A chain of alternates is a screen nobody designed.
        (
            "nested",
            ImportInputSpec(
                kind="path",
                label="Path",
                field="library_path",
                alternate=ImportInputSpec(kind="upload", label="Deeper", field="deeper"),
            ),
        ),
        # Two inputs that post the same field are one input with a bug.
        ("colliding_field", ImportInputSpec(kind="path", label="Path", field="file")),
    ],
)
def test_the_suite_rejects_a_malformed_alternate(name: str, alternate: ImportInputSpec) -> None:
    class Malformed(_DeclaringImporter):
        input = replace(_DeclaringImporter.input, alternate=alternate)

    with pytest.raises(AssertionError):
        assert_declared_guidance(Malformed())


@pytest.mark.parametrize(("field", "value"), [("max_bytes", 0), ("max_files", -1)])
def test_the_suite_rejects_a_nonsense_envelope(field: str, value: int) -> None:
    """A cap of zero refuses everything; a negative one is a typo, not a policy."""

    class Malformed(_DeclaringImporter):
        input = replace(_DeclaringImporter.input, **{field: value})

    with pytest.raises(AssertionError):
        assert_declared_guidance(Malformed())


def test_a_directory_connector_must_be_able_to_read_a_set_of_files() -> None:
    """`kind="directory"` is a promise about `read`, not only about the screen."""

    class NoFileSupport(_DeclaringImporter):
        input = replace(_DeclaringImporter.input, kind="directory", accepts_files=False)

    with pytest.raises(AssertionError):
        assert_declared_guidance(NoFileSupport())


def test_a_directory_connector_declares_what_its_bundle_may_contain() -> None:
    """The shared route refuses a member before writing a byte, and only the
    connector knows what its source is shaped like (DEC-083)."""

    class NoMembers(_DeclaringImporter):
        input = replace(_DeclaringImporter.input, kind="directory", accepts_files=True, members=())

    with pytest.raises(AssertionError):
        assert_declared_guidance(NoMembers())


@pytest.mark.parametrize(
    "pattern",
    [
        "/etc/passwd",
        "../escape/cover.jpg",
        "books/../cover.jpg",
        ".caltrash/**/cover.jpg",
        "**",
        "books/**/cover.jpg",
        "",
        "   ",
    ],
)
def test_the_suite_rejects_a_malformed_bundle_member_pattern(pattern: str) -> None:
    """A pattern that can escape, or that matches everything, is not a declaration.

    `**` is meaningful only as the leading segment: anywhere else it is a wildcard
    the matcher does not implement, and silently never matching would look like a
    connector that simply refuses its own files.
    """

    class Malformed(_DeclaringImporter):
        input = replace(
            _DeclaringImporter.input,
            kind="directory",
            accepts_files=True,
            members=(pattern,),
        )

    with pytest.raises(AssertionError):
        assert_declared_guidance(Malformed())


def test_a_well_formed_member_declaration_passes() -> None:
    class Declared(_DeclaringImporter):
        input = replace(
            _DeclaringImporter.input,
            kind="directory",
            accepts_files=True,
            members=("metadata.db", "**/cover.jpg", "**/*.epub"),
        )

    assert_declared_guidance(Declared())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # A guide is ordered steps, not prose and not a blank line.
        ("guide", "Open the export page."),
        ("guide", ("Open the export page.", "   ")),
        ("empty_state", "   "),
        # Anything a screen turns into a link leaves the LAN, so it is https or
        # it is not published at all.
        ("help_url", "http://example.invalid/export"),
        ("help_url", "javascript:alert(1)"),
        # Only a source that is a place can be browsed into.
        ("browsable", True),
    ],
)
def test_the_suite_rejects_a_malformed_declaration(field: str, value: object) -> None:
    class Malformed(_DeclaringImporter):
        input = replace(_DeclaringImporter.input, **{field: value})

    with pytest.raises(AssertionError):
        assert_declared_guidance(Malformed())


def test_the_suite_rejects_an_empty_or_malformed_error_vocabulary() -> None:
    class NoCodes(_DeclaringImporter):
        error_codes = frozenset()

    class ShoutedCode(_DeclaringImporter):
        error_codes = frozenset({"Invalid Source"})

    for broken in (NoCodes(), ShoutedCode()):
        with pytest.raises(AssertionError):
            assert_declared_guidance(broken)


def test_an_undeclared_error_code_never_reaches_a_reader_as_itself() -> None:
    """The closed set is enforced, not merely declared.

    A connector that raises a code its declaration does not list is a defect in
    the connector, and the screen has no copy for it. It is republished under one
    stable code instead of leaking an unknown vocabulary to the client.
    """
    importer = _DeclaringImporter()
    declared = ImportReadError("invalid_source", "Bad file", user_message="Pick a CSV.")
    assert declared_read_error(importer, declared) is declared

    smuggled = ImportReadError(
        "surprise", "Something else", details={"row": 4}, action="Try again."
    )
    published = declared_read_error(importer, smuggled)
    assert published.code == "undeclared_import_error"
    assert published.details == {"row": 4}
    assert published.action == "Try again."


def test_the_suite_rejects_incremental_without_a_plan_method() -> None:
    class Claims(_DeclaringImporter):
        input = replace(_DeclaringImporter.input, incremental=True)

    with pytest.raises(AssertionError):
        assert_declared_guidance(Claims())


def test_a_plan_may_only_want_what_it_was_offered() -> None:
    """The plan decides what to send; it does not get to invent a path.

    A connector that names something the client never offered would have the client
    upload a file it did not choose, which is the client's business and not the
    connector's. Enforced at the boundary rather than trusted.
    """
    candidates = (
        ImportCandidate(path="metadata.db", size=10),
        ImportCandidate(path="A/B (1)/cover.jpg", size=20),
    )
    honest = ImportPlan(wanted=("metadata.db",), holding=1)
    assert planned_upload(candidates, honest).wanted == ("metadata.db",)

    with pytest.raises(ValueError, match="was not offered"):
        planned_upload(candidates, ImportPlan(wanted=("/etc/passwd",), holding=0))
    with pytest.raises(ValueError, match="was not offered"):
        planned_upload(candidates, ImportPlan(wanted=("A/Other (2)/cover.jpg",), holding=0))


def test_every_registered_importer_declares_its_error_vocabulary() -> None:
    """A connector's codes are its own, and every one of them is declared."""
    assert IMPORTERS["goodreads"].error_codes
    assert IMPORTERS["calibre"].error_codes
    assert "calibre_library_not_found" in IMPORTERS["calibre"].error_codes
    # Calibre leads with the folder chooser; the mount is its alternate (DEC-081).
    assert IMPORTERS["calibre"].input.kind == "directory"
    assert IMPORTERS["calibre"].input.accepts_files is True
    assert IMPORTERS["calibre"].input.alternate is not None
    assert IMPORTERS["calibre"].input.alternate.browsable is True
    assert IMPORTERS["goodreads"].input.browsable is False
    assert IMPORTERS["goodreads"].input.alternate is None


def test_the_suite_covers_every_field_of_the_contract() -> None:
    """The contract is `Domain`'s fields; a new one must arrive with a check.

    Without this, a seam added later is a field nothing verifies, and the suite silently
    stops describing the contract it claims to describe.
    """
    covered = {
        "item_type": "the_domain_names_itself",
        "label": "the_domain_names_itself",
        "entry_panel_label": "the_domain_names_itself",
        "statuses": "statuses_are_a_usable_vocabulary",
        "default_status": "statuses_are_a_usable_vocabulary",
        "formats": "formats_are_a_usable_vocabulary",
        "entry_fields": "entry_fields_are_passage_fields",
        "entry_field_labels": "entry_field_labels_name_fields_this_domain_has",
        "fields": "fields_are_described_completely",
        "identity": "identity_is_a_strategy",
        "recognize": "the_recognizer_answers_for_any_string",
        "chooses_covers": "the_cover_chooser_is_only_declared_where_it_can_work",
        "enrichment": "enrichment_is_answerable_by_this_domain",
        "progress": "progress_counts_something_this_domain_declares",
    }
    declared = set(Domain.__dataclass_fields__)
    assert declared == set(covered), (
        f"`Domain` gained or lost a field: {declared ^ set(covered)}. "
        "Add a conformance check for it, or record here why it needs none."
    )
    for field, check in covered.items():
        if check is not None:
            assert check in REGISTRY_CHECKS, f"{field} names a check that does not exist"


def test_the_suite_has_an_application_wiring_tier() -> None:
    assert set(APP_CHECKS) == {
        "declared_providers_are_constructed_for_this_domain",
        "recognized_provider_routes_are_constructed_for_this_domain",
        "cover_choice_has_a_provider_that_can_offer_candidates",
    }


# --------------------------------------------------------------------------------------
# A domain that does not exist, so the suite can be shown to fail
# --------------------------------------------------------------------------------------


def a_third_domain(**overrides: object) -> Domain:
    """The smallest thing that satisfies the contract, without being registered.

    Shaped on games, because that is the domain DEC-052 predicted would need no seam
    albums did not — but nothing here is IGDB-specific. It is the fixture the malformed
    variants below are made from.
    """
    base: dict[str, object] = {
        "item_type": "game",
        "label": "Game",
        "identity": IdentityStrategy(lambda _candidate: None, ("igdb",)),
        "fields": (
            FieldSpec("creators", "Studios", multiplicity="many"),
            FieldSpec("platform", "Platform"),
        ),
        "enrichment": None,
        "statuses": (
            StatusSpec("unsorted", "Inbox", choosable=False, hotkey="u"),
            StatusSpec("wishlist", "Wishlist", hotkey="w"),
            StatusSpec("owned", "Owned", hotkey="o"),
        ),
        "default_status": "owned",
        "entry_fields": frozenset({"date_finished"}),
        "formats": (FormatSpec("digital", "Digital"),),
        "entry_panel_label": "Your copy",
        "recognize": lambda _value: None,
        # Nothing supplies game covers through Open Library's work-editions path.
        "chooses_covers": False,
    }
    return Domain(**{**base, **overrides})  # type: ignore[arg-type]


@pytest.mark.parametrize("name", sorted(REGISTRY_CHECKS))
def test_a_domain_that_does_not_exist_yet_satisfies_the_contract_alone(name: str) -> None:
    """A domain can be *written* against this contract with nothing else in hand.

    This is the half of the promise that already holds: everything in `REGISTRY_CHECKS`
    is satisfiable by a domain nobody has registered, which is what makes the contract a
    contract rather than a description of books and albums.
    """
    REGISTRY_CHECKS[name](a_third_domain())


def test_the_core_now_hosts_a_status_no_registered_domain_declares(migrated: Engine) -> None:
    """The measurement, and then the repair. **This test was written to flip, and did.**

    Phase A asserted the opposite: a third domain declaring `playing` was refused twice
    over, by the published union and by the database. DEC-067 costed the two separately
    and they were answered differently, which is the point of pricing them apart —
    `ck_entries_status` was dropped in `0014_status_is_the_domains` because a per-domain
    migration on a shared table is a real barrier, and the hand-spelled unions were kept
    because three lines caught by a test are cheaper than any way of removing them.
    """
    # Derived rather than written: `playing` was the example while books and albums were
    # the only domains, and a real games domain registering it would have broken this
    # test's premise rather than its point. A dry run of the contributor guide did
    # exactly that. The value only has to be one no registered domain declares.
    unclaimed = next(
        value
        for value in (f"conformance_status_{index}" for index in range(100))
        if value not in ALL_STATUSES
    )
    with_its_own_status = a_third_domain(
        statuses=(
            StatusSpec("unsorted", "Inbox", choosable=False, hotkey="u"),
            StatusSpec(unclaimed, "Something of its own", hotkey="q"),
        ),
        default_status=unclaimed,
    )
    # It is internally consistent: nothing about the domain itself is wrong.
    for check in REGISTRY_CHECKS.values():
        check(with_its_own_status)

    # The database now takes whatever a domain declares: adding a domain is no longer a
    # schema change, and two domain teams no longer collide on one alembic head.
    CORE_CHECKS["the_database_accepts_every_declared_status"](with_its_own_status, migrated)
    # The published union is still a hand-spelled line per value, deliberately (row 2).
    with pytest.raises(AssertionError, match="EntryStatus"):
        CORE_CHECKS["the_published_unions_carry_this_domain"](with_its_own_status, migrated)


MALFORMED: list[tuple[str, str, Domain]] = [
    (
        "statuses_are_a_usable_vocabulary",
        "a status with no label",
        a_third_domain(
            statuses=(
                StatusSpec("unsorted", "Inbox", choosable=False, hotkey="u"),
                StatusSpec("owned", "", hotkey="o"),
            )
        ),
    ),
    (
        "statuses_are_a_usable_vocabulary",
        "a default outside the vocabulary",
        a_third_domain(default_status="read"),
    ),
    (
        "statuses_are_a_usable_vocabulary",
        "no inbox to import into",
        a_third_domain(
            statuses=(StatusSpec("owned", "Owned", hotkey="o"),), default_status="owned"
        ),
    ),
    (
        "statuses_are_a_usable_vocabulary",
        "one triage key bound twice",
        a_third_domain(
            statuses=(
                StatusSpec("unsorted", "Inbox", choosable=False, hotkey="u"),
                StatusSpec("wishlist", "Wishlist", hotkey="o"),
                StatusSpec("owned", "Owned", hotkey="o"),
            )
        ),
    ),
    (
        "formats_are_a_usable_vocabulary",
        "no format vocabulary at all",
        a_third_domain(formats=()),
    ),
    (
        "entry_fields_are_passage_fields",
        "an entry field that does not exist",
        a_third_domain(entry_fields=frozenset({"hours_played"})),
    ),
    (
        "fields_are_described_completely",
        "a rows field with no columns",
        a_third_domain(
            fields=(FieldSpec("achievements", "Achievements", type="rows", multiplicity="many"),)
        ),
    ),
    (
        "fields_are_described_completely",
        "metadata shadowing a neutral item column",
        a_third_domain(fields=(FieldSpec("title", "Title"),)),
    ),
    (
        "identity_is_a_strategy",
        "an identity with no source preference",
        a_third_domain(identity=IdentityStrategy(lambda _candidate: None, ())),
    ),
    (
        "the_recognizer_answers_for_any_string",
        "a recognizer that raises on a malformed URL",
        a_third_domain(recognize=lambda value: UrlMatch("igdb", "fetch", value.split("//")[1])),
    ),
    (
        "the_domain_names_itself",
        "an item type that is not storable",
        a_third_domain(item_type="Board Game"),
    ),
    (
        "the_cover_chooser_is_only_declared_where_it_can_work",
        "a chooser no provider can serve",
        a_third_domain(chooses_covers=True),
    ),
    (
        "entry_field_labels_name_fields_this_domain_has",
        "a label for a passage field the domain does not have",
        # The fixture declares `date_finished` alone, so this names a field that will
        # never render — which looks identical to a label that is not working.
        a_third_domain(entry_field_labels={"reread_count": "Replays"}),
    ),
    (
        "entry_field_labels_name_fields_this_domain_has",
        "a bare entry field label",
        a_third_domain(entry_field_labels={"date_finished": "   "}),
    ),
    (
        "enrichment_is_answerable_by_this_domain",
        "enrichment with nobody to ask",
        a_third_domain(
            enrichment=EnrichmentSpec("igdb_id", (), ("platform",)),
        ),
    ),
    (
        "enrichment_is_answerable_by_this_domain",
        "an incompleteness rule naming a field this domain does not have",
        # The anime bug, as a fixture: `description` is a book's field, and a domain
        # that judges itself by one it never stores is never complete.
        a_third_domain(
            enrichment=EnrichmentSpec("igdb_id", ("igdb",), ("description",)),
        ),
    ),
    (
        "enrichment_is_answerable_by_this_domain",
        "enrichment nothing would ever complete",
        a_third_domain(enrichment=EnrichmentSpec("igdb_id", ("igdb",), ())),
    ),
    (
        "progress_counts_something_this_domain_declares",
        "progress towards a total the domain does not store",
        a_third_domain(progress=ProgressSpec("Completion", "percent", "hours_to_beat")),
    ),
    (
        "progress_counts_something_this_domain_declares",
        "progress towards a field that is not a number",
        # The fixture declares `platform` as text, so a total could never be read off it.
        a_third_domain(progress=ProgressSpec("Completion", "percent", "platform")),
    ),
    (
        "progress_counts_something_this_domain_declares",
        "a progress count with nothing to call it",
        a_third_domain(progress=ProgressSpec("   ", "percent")),
    ),
]


@pytest.mark.parametrize(
    ("name", "domain"),
    [(name, domain) for name, _label, domain in MALFORMED],
    ids=[f"{name}-{label}" for name, label, _domain in MALFORMED],
)
def test_the_suite_rejects_a_malformed_domain(name: str, domain: Domain) -> None:
    """The acceptance criterion that keeps the suite honest.

    Every check above must be able to fail. A suite that only restates the dataclass
    would pass this file's first half and prove nothing at all.
    """
    with pytest.raises(AssertionError):
        REGISTRY_CHECKS[name](domain)


class _CatalogProvider:
    name = "igdb"
    item_type = "game"


@pytest.mark.parametrize(
    ("name", "domain", "catalog"),
    [
        (
            "declared_providers_are_constructed_for_this_domain",
            a_third_domain(),
            {},
        ),
        (
            "recognized_provider_routes_are_constructed_for_this_domain",
            a_third_domain(recognize=lambda value: UrlMatch("ghost", "fetch", value)),
            {"igdb": _CatalogProvider()},
        ),
        (
            "cover_choice_has_a_provider_that_can_offer_candidates",
            a_third_domain(chooses_covers=True),
            {"igdb": _CatalogProvider()},
        ),
    ],
)
def test_the_application_tier_rejects_broken_wiring(
    name: str, domain: Domain, catalog: dict[str, object]
) -> None:
    app = create_app(Settings(user_agent_contact="test@example.invalid"))
    app.state.provider_catalog = catalog
    with pytest.raises(AssertionError):
        APP_CHECKS[name](domain, app)


# --------------------------------------------------------------------------------------
# The API refuses what the domain does not declare
# --------------------------------------------------------------------------------------


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("domain", list(DOMAINS.values()), ids=lambda row: str(row.item_type))
async def test_the_api_refuses_a_status_this_domain_does_not_declare(
    domain: Domain, tmp_path: Path
) -> None:
    """A write is validated against the item's own domain, and refused naming it.

    Parametrized rather than written twice, so a third domain inherits the assertion.
    The foreign status is taken from another registered domain, which is what makes this
    a per-domain rule rather than a global vocabulary: the value is perfectly valid one
    row further down the library.
    """
    foreign = next(
        (
            status.value
            for other in DOMAINS.values()
            if other.item_type != domain.item_type
            for status in other.statuses
            if domain.status(status.value) is None
        ),
        None,
    )
    if foreign is None:
        pytest.skip(f"no other registered domain has a status {domain.item_type} lacks")

    settings = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        repository = DomainRepository(app.state.engine)
        created = repository.create_or_get_entry(title="Conformance", creators=("Nobody",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE items SET type=:type WHERE id=:id"),
                {"type": domain.item_type, "id": created.item_id},
            )
        response = await client.patch(f"/api/entries/{created.entry_id}", json={"status": foreign})

    assert response.status_code == 422, response.text
    body = response.json()["error"]
    assert body["code"] == "invalid_status"
    assert domain.label in body["message"], (
        "the refusal must name the domain: the value is valid elsewhere in the library"
    )


# --------------------------------------------------------------------------------------
# The shared layer isolates one domain's mistake from every other domain
# --------------------------------------------------------------------------------------


class _StubProvider:
    """Enough of `Provider` for `resolve_input` to spend a match on."""

    name = "stub"
    item_type = "game"

    async def search(self, query: str, limit: int = 20) -> list[SearchCandidate]:
        raise AssertionError("not reached")

    async def fetch(self, source_id: str) -> ItemPayload:
        return ItemPayload(
            source="stub",
            source_id=source_id,
            source_refs=(),
            title="Resolved anyway",
            subtitle=None,
            creators=(),
            year=None,
            cover_url=None,
            identifiers={},
            language=None,
            metadata={},
        )


@pytest.mark.anyio
async def test_a_broken_recognizer_does_not_deny_another_domain_its_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The epic's promise, as the smallest test that can hold it.

    `resolve_input` asks every registered domain what a pasted string means, in registry
    order. If one domain's recognizer raises, the loop must not end there — a domain
    added by one team cannot be allowed to break the add box for a domain added by
    another. The recognizer itself is still wrong, which is what the conformance suite
    catches; this is the shared layer refusing to make it everyone's problem.
    """

    def explode(_value: str) -> UrlMatch | None:
        raise ValueError("this domain's recognizer is broken")

    registry = {
        "broken": a_third_domain(item_type="broken", recognize=explode),
        "game": a_third_domain(recognize=lambda value: UrlMatch("stub", "fetch", value)),
    }
    monkeypatch.setattr("book_tracker.application.providers.DOMAINS", registry)

    resolved = await resolve_input("anything at all", {"stub": _StubProvider()})  # type: ignore[dict-item]

    assert [row.title for row in resolved] == ["Resolved anyway"]
