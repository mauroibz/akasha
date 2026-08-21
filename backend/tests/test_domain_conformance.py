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
from pathlib import Path

import httpx
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from book_tracker.application.providers import resolve_input
from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.importers import Importer, ImportInputSpec
from book_tracker.domain.providers import IdentityStrategy, ItemPayload, SearchCandidate
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
    FieldSpec,
    FormatSpec,
    StatusSpec,
    UrlMatch,
)
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app
from book_tracker.migrations import upgrade

RegistryCheck = Callable[[Domain], None]
CoreCheck = Callable[[Domain, Engine], None]

REGISTRY_CHECKS: dict[str, RegistryCheck] = {}
CORE_CHECKS: dict[str, CoreCheck] = {}


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


def registry_check(function: RegistryCheck) -> RegistryCheck:
    REGISTRY_CHECKS[function.__name__] = function
    return function


def core_check(function: CoreCheck) -> CoreCheck:
    CORE_CHECKS[function.__name__] = function
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
    probes = (
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
        "https://musicbrainz.org/release-group/00000000-0000-0000-0000-000000000000",
        "https://books.google.com/books?id=zyTCAlFPjgYC",
        "a" * 4000,
    )
    for probe in probes:
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
        "fields": "fields_are_described_completely",
        "identity": "identity_is_a_strategy",
        "recognize": "the_recognizer_answers_for_any_string",
        "chooses_covers": "the_cover_chooser_is_only_declared_where_it_can_work",
        # Declarative and checked by the enrichment path rather than by shape: a domain
        # that does not enrich is queued no jobs (`_backfillable_items`).
        "enriches": None,
    }
    declared = set(Domain.__dataclass_fields__)
    assert declared == set(covered), (
        f"`Domain` gained or lost a field: {declared ^ set(covered)}. "
        "Add a conformance check for it, or record here why it needs none."
    )
    for field, check in covered.items():
        if check is not None:
            assert check in REGISTRY_CHECKS, f"{field} names a check that does not exist"


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
        "enriches": False,
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
