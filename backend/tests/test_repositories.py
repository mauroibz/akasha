from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select

from book_tracker.config import Settings
from book_tracker.database import create_engine
from book_tracker.domain.identity import normalize_identifier
from book_tracker.domain.matching import MatchKind
from book_tracker.infrastructure.models import EntryRow, ItemIdentifierRow, ItemRow, ShelfRow
from book_tracker.infrastructure.repositories import DomainRepository, IdentityConflict
from book_tracker.migrations import upgrade


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    value = create_engine(configured)
    yield value
    value.dispose()


def test_exact_item_and_entry_deduplicate(engine: Engine) -> None:
    repository = DomainRepository(engine)
    identity = normalize_identifier("isbn", "0-306-40615-2")
    first = repository.create_or_get_entry(title="First", identifiers=(identity,))
    second = repository.create_or_get_entry(title="Ignored", identifiers=(identity,))
    assert first.item_id == second.item_id
    assert first.entry_id == second.entry_id
    assert second.already_exists


def test_concurrent_equivalent_isbns_create_one_item(engine: Engine) -> None:
    def create(value: str) -> int:
        result = DomainRepository(engine).create_or_get_entry(
            title="Physics", identifiers=(normalize_identifier("isbn", value),)
        )
        return result.item_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = set(pool.map(create, ["0-306-40615-2", "9780306406157"]))
    assert len(ids) == 1
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(ItemRow)) == 1


def test_split_exact_identities_conflict_without_mutation(engine: Engine) -> None:
    repository = DomainRepository(engine)
    one = normalize_identifier("calibre_uuid", "one")
    two = normalize_identifier("calibre_uuid", "two")
    repository.create_or_get_entry(title="One", identifiers=(one,))
    repository.create_or_get_entry(title="Two", identifiers=(two,))
    with pytest.raises(IdentityConflict) as error:
        repository.create_or_get_entry(title="Contradiction", identifiers=(one, two))
    assert error.value.decision.kind is MatchKind.IDENTITY_CONFLICT
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(ItemRow)) == 2
        assert connection.scalar(select(func.count()).select_from(ItemIdentifierRow)) == 2


def test_title_author_is_only_an_ambiguity_suggestion(engine: Engine) -> None:
    repository = DomainRepository(engine)
    repository.create_or_get_entry(title="Cien años de soledad", authors=("García Márquez",))
    decision = repository.match(title="Cien anos de soledad!", first_author="Garcia Marquez")
    assert decision.kind is MatchKind.AMBIGUOUS
    assert decision.item_id is None


def test_fill_empty_and_identifier_union_require_exact_agreement(engine: Engine) -> None:
    repository = DomainRepository(engine)
    isbn = normalize_identifier("isbn", "9780306406157")
    calibre = normalize_identifier("calibre_uuid", "abc")
    created = repository.create_or_get_entry(
        title="Existing", subtitle=None, authors=("Author",), identifiers=(isbn,)
    )
    repository.fill_empty_item(
        created.item_id, {"title": "Incoming", "subtitle": "Sub"}, (isbn, calibre)
    )
    with engine.connect() as connection:
        item = connection.execute(
            select(ItemRow.title, ItemRow.subtitle).where(ItemRow.id == created.item_id)
        ).one()
        assert item.title == "Existing"
        assert item.subtitle == "Sub"
        assert connection.scalar(select(func.count()).select_from(ItemIdentifierRow)) == 2


def test_shelf_lifecycle_scopes_slug_and_only_cascades_joins(engine: Engine) -> None:
    repository = DomainRepository(engine)
    entry = repository.create_or_get_entry(title="Book")
    shelf = repository.create_shelf("Sci Fi")
    repository.attach_shelf(entry.entry_id, shelf)
    renamed = repository.rename_shelf(shelf, "Science Fiction")
    assert renamed.slug == "science-fiction"
    with pytest.raises(ValueError):
        repository.create_shelf("Science Fiction")
    repository.delete_shelf(shelf)
    with engine.connect() as connection:
        assert (
            connection.scalar(select(EntryRow.id).where(EntryRow.id == entry.entry_id)) is not None
        )
        assert connection.scalar(select(ShelfRow.id).where(ShelfRow.id == shelf)) is None
