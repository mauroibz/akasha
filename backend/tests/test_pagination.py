import base64
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.domain.pagination import CursorError, CursorState, decode_cursor, encode_cursor
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


def test_cursor_is_opaque_versioned_and_bound_to_query() -> None:
    cursor = encode_cursor(
        CursorState(
            sort="score", order="desc", filter_key="abc", value=8, entry_id=4, null_bucket=0
        )
    )
    assert "," not in cursor
    assert decode_cursor(cursor, sort="score", order="desc", filter_key="abc").entry_id == 4
    with pytest.raises(CursorError):
        decode_cursor(cursor, sort="title", order="desc", filter_key="abc")
    payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    payload["v"] = 99
    invalid = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    with pytest.raises(CursorError):
        decode_cursor(invalid, sort="score", order="desc", filter_key="abc")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_list_filters_facets_and_default_excludes_unsorted(tmp_path: Path) -> None:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    app = create_app(configured)
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        first = repository.create_or_get_entry(title="Álgebra", creators=("Ada",))
        second = repository.create_or_get_entry(title="Biology", creators=("Bob",))
        third = repository.create_or_get_entry(title="Chemistry", creators=("Cara",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET status='read', score=8 WHERE id=:id"),
                {"id": first.entry_id},
            )
            connection.execute(
                text("UPDATE entries SET status='reading', score=8 WHERE id=:id"),
                {"id": second.entry_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            default = await client.get("/api/entries")
            assert default.status_code == 200
            assert default.json()["total"] == 2
            assert default.json()["facets"]["status_counts"] == {
                "read": 1,
                "reading": 1,
                "unsorted": 1,
            }
            explicit = await client.get("/api/entries", params=[("status", "unsorted")])
            assert [row["id"] for row in explicit.json()["items"]] == [third.entry_id]
            searched = await client.get("/api/entries", params={"q": "algebra"})
            assert [row["id"] for row in searched.json()["items"]] == [first.entry_id]


@pytest.mark.anyio
@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_keyset_score_is_null_last_and_stable_after_deleted_boundary(
    tmp_path: Path, order: str
) -> None:
    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    app = create_app(configured)
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        entries = [repository.create_or_get_entry(title=f"Book {index}") for index in range(5)]
        with app.state.engine.begin() as connection:
            for result, score in zip(entries, [8, 8, 3, None, None], strict=True):
                connection.execute(
                    text("UPDATE entries SET status='read', score=:score WHERE id=:id"),
                    {"score": score, "id": result.entry_id},
                )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            params = {"sort": "score", "order": order, "limit": 2}
            first = (await client.get("/api/entries", params=params)).json()
            assert all(row["score"] is not None for row in first["items"])
            boundary = first["items"][-1]["id"]
            await client.delete(f"/api/entries/{boundary}")
            seen = [row["id"] for row in first["items"][:-1]]
            cursor = first["next_cursor"]
            while cursor:
                page = (await client.get("/api/entries", params={**params, "after": cursor})).json()
                seen.extend(row["id"] for row in page["items"])
                cursor = page["next_cursor"]
            assert len(seen) == len(set(seen)) == 4
            scores = [
                (await client.get(f"/api/entries/{entry_id}")).json()["score"] for entry_id in seen
            ]
            assert scores[-2:] == [None, None]


@pytest.mark.anyio
async def test_malformed_or_mismatched_cursor_returns_stable_error(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        malformed = await client.get("/api/entries", params={"after": "not-json"})
        assert malformed.status_code == 400
        assert malformed.json()["error"]["code"] == "invalid_cursor"


def test_common_status_date_query_uses_composite_index(tmp_path: Path) -> None:
    from book_tracker.database import create_engine
    from book_tracker.migrations import upgrade

    configured = Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")
    assert configured.database_url is not None
    upgrade(configured.database_url)
    engine = create_engine(configured)
    with engine.connect() as connection:
        plan = " ".join(
            row[3]
            for row in connection.execute(
                text(
                    "EXPLAIN QUERY PLAN SELECT id FROM entries "
                    "WHERE user_id=1 AND status='read' "
                    "ORDER BY date_added DESC, id DESC LIMIT 100"
                )
            )
        )
    assert "ix_entries_user_status_date_id" in plan


@pytest.mark.anyio
@pytest.mark.parametrize(
    "sort", ["date_added", "score", "title", "creator", "year", "date_finished"]
)
@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_every_sort_pages_without_duplicates_and_keeps_nulls_last(
    tmp_path: Path, sort: str, order: str
) -> None:
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        entries = [
            repository.create_or_get_entry(title="Same", creators=("Zed",)),
            repository.create_or_get_entry(title="same", creators=("Zed",)),
            repository.create_or_get_entry(title="Other"),
        ]
        with app.state.engine.begin() as connection:
            connection.execute(text("UPDATE entries SET status='read'"))
            connection.execute(
                text(
                    "UPDATE entries SET score=5,date_finished='2020-01-01' WHERE id IN (:one,:two)"
                ),
                {"one": entries[0].entry_id, "two": entries[1].entry_id},
            )
            connection.execute(
                text("UPDATE items SET year=2000 WHERE id IN (:one,:two)"),
                {"one": entries[0].item_id, "two": entries[1].item_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            cursor = None
            rows = []
            while True:
                params = {"sort": sort, "order": order, "limit": 1}
                if cursor:
                    params["after"] = cursor
                page = (await client.get("/api/entries", params=params)).json()
                rows.extend(page["items"])
                cursor = page["next_cursor"]
                if cursor is None:
                    break
            assert len({row["id"] for row in rows}) == len(rows) == 3
            if sort in {"score", "creator", "year", "date_finished"}:
                value = "item" if sort in {"creator", "year"} else None
                values = [row[value][sort] if value else row[sort] for row in rows]
                assert values[-1] is None


def test_a_cursor_from_before_the_creator_sort_projection_is_rejected() -> None:
    """A pre-0011 cursor carries a value from the old projection.

    The creator sort used to order by the first author verbatim, so a stale cursor
    holds "gabriel" where the column now holds "garcia marquez gabriel". Comparing
    the two would silently skip or repeat a page, which is worse than an error the
    library page already knows how to render.
    """
    stale = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "sort": "creator",
                    "order": "asc",
                    "filter_key": "abc",
                    "value": "gabriel",
                    "entry_id": 4,
                    "null_bucket": 0,
                    "v": 1,
                }
            ).encode()
        )
        .decode()
        .rstrip("=")
    )
    with pytest.raises(CursorError):
        decode_cursor(stale, sort="creator", order="asc", filter_key="abc")


@pytest.mark.anyio
async def test_author_sort_orders_by_the_creator_sort_name(tmp_path: Path) -> None:
    """The three names the roadmap named, plus one whose two orderings disagree.

    Sorting by given name and sorting by surname happen to agree for García
    Márquez, Bioy Casares and Rulfo — a, g, j against b, g, r — so a test built
    only from those three passes against the defect it is meant to catch. Zoé
    Aguirre is the one that separates them: last by given name, first by surname.
    """
    app = create_app(Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid"))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        for title, author in [
            ("Cien años de soledad", "Gabriel García Márquez"),
            ("La invención de Morel", "Adolfo Bioy Casares"),
            ("Pedro Páramo", "Juan Rulfo"),
            ("Sangre azul", "Zoé Aguirre"),
        ]:
            repository.create_or_get_entry(title=title, creators=(author,))
        with app.state.engine.begin() as connection:
            connection.execute(text("UPDATE entries SET status='read'"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            page = (
                await client.get("/api/entries", params={"sort": "creator", "order": "asc"})
            ).json()
    assert [row["item"]["title"] for row in page["items"]] == [
        "Sangre azul",
        "La invención de Morel",
        "Cien años de soledad",
        "Pedro Páramo",
    ]
