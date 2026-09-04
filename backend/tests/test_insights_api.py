"""Sprint 065: `GET /api/insights` over HTTP — validation and the zero-score case.

Same fixture shape as `test_library_api.py`: a real app via `create_app`'s lifespan,
`DomainRepository` to seed, `httpx.AsyncClient` against the ASGI app directly.
"""

from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from book_tracker.config import Settings
from book_tracker.infrastructure.repositories import DomainRepository
from book_tracker.main import create_app


def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, user_agent_contact="test@example.invalid")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_a_groupable_key_ranks_over_http(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        entry = repository.create_or_get_entry(title="Rayuela", creators=("Julio Cortázar",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/insights", params={"type": "book", "key": "creators", "metric": "count"}
            )
    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == [
        {
            "key": "julio cortazar",
            "label": "Julio Cortázar",
            "count": 1,
            "rated_count": 0,
            "mean_score": None,
            "score_spread": None,
            "covers": [],
        }
    ]
    assert body["total_entries"] == 1
    assert body["rated_entries"] == 0


@pytest.mark.anyio
async def test_an_unknown_domain_type_is_a_422(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get(
            "/api/insights", params={"type": "boardgame", "key": "creators"}
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_a_key_the_domain_does_not_declare_groupable_is_a_422_naming_the_domain(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/insights", params={"type": "book", "key": "description"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_insight_key"
    assert "Book" in body["error"]["message"]


@pytest.mark.anyio
async def test_a_zero_score_domain_reports_no_rated_groups_over_http(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        entry = repository.create_or_get_entry(title="Unrated", creators=("Nobody Rated",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET status='read' WHERE id=:id"), {"id": entry.entry_id}
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            count_response = await client.get(
                "/api/insights", params={"type": "book", "key": "creators", "metric": "count"}
            )
            score_response = await client.get(
                "/api/insights", params={"type": "book", "key": "creators", "metric": "score"}
            )
    assert count_response.json()["rows"]
    assert score_response.json()["rows"] == []
    assert score_response.json()["no_rated_groups"] is True


@pytest.mark.anyio
async def test_item_types_publishes_which_fields_are_groupable(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        response = await client.get("/api/item-types")
    book = next(domain for domain in response.json() if domain["id"] == "book")
    fields = {field["name"]: field["groupable"] for field in book["fields"]}
    assert fields["creators"] is True
    assert fields["description"] is False


@pytest.mark.anyio
async def test_the_built_in_year_and_decade_keys_rank_over_http(tmp_path: Path) -> None:
    """Sprint 066 walkthrough: `key=year` answered 500, not a ranking.

    `rank()` builds a numeric key straight from `items.year`, and
    `InsightRowResponse.key` declares a string, so every year row failed response
    validation. Sprint 065's AC3 was proven at the repository layer only, where an
    `int` is a perfectly good grouping value; nothing exercised either built-in key
    over HTTP. `/api/entries`' own `key`/`value` filter already `int()`s what it is
    given, so a string is the contract both halves were written for.
    """
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        for title, year in (("Rayuela", 1963), ("Bestiario", 1951), ("Final del juego", 1956)):
            entry = repository.create_or_get_entry(title=title, creators=("Julio Cortázar",))
            with app.state.engine.begin() as connection:
                connection.execute(
                    text("UPDATE items SET year=:year WHERE id=:id"),
                    {"year": year, "id": entry.item_id},
                )
                connection.execute(
                    text("UPDATE entries SET status='read' WHERE id=:id"),
                    {"id": entry.entry_id},
                )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            years = await client.get(
                "/api/insights", params={"type": "book", "key": "year", "metric": "count"}
            )
            decades = await client.get(
                "/api/insights", params={"type": "book", "key": "decade", "metric": "count"}
            )

    assert years.status_code == 200, years.text
    assert [(row["key"], row["label"], row["count"]) for row in years.json()["rows"]] == [
        ("1951", "1951", 1),
        ("1956", "1956", 1),
        ("1963", "1963", 1),
    ]

    assert decades.status_code == 200, decades.text
    assert [(row["key"], row["label"], row["count"]) for row in decades.json()["rows"]] == [
        ("1950", "1950s", 2),
        ("1960", "1960s", 1),
    ]


@pytest.mark.anyio
async def test_a_year_ranking_row_filters_the_library_to_its_members(tmp_path: Path) -> None:
    """The key a year row hands back is the value `/api/entries` expects (AC8)."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        for title, year in (("Rayuela", 1963), ("Bestiario", 1951)):
            entry = repository.create_or_get_entry(title=title, creators=("Julio Cortázar",))
            with app.state.engine.begin() as connection:
                connection.execute(
                    text("UPDATE items SET year=:year WHERE id=:id"),
                    {"year": year, "id": entry.item_id},
                )
                connection.execute(
                    text("UPDATE entries SET status='read' WHERE id=:id"),
                    {"id": entry.entry_id},
                )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            ranking = await client.get(
                "/api/insights", params={"type": "book", "key": "year", "metric": "count"}
            )
            row = ranking.json()["rows"][0]
            members = await client.get(
                "/api/entries",
                params={"type": "book", "key": "year", "value": row["key"]},
            )

    assert members.status_code == 200, members.text
    titles = [item["item"]["title"] for item in members.json()["items"]]
    assert titles == ["Bestiario"]


@pytest.mark.anyio
async def test_a_status_filter_narrows_a_ranking_and_agrees_with_entries(tmp_path: Path) -> None:
    """Sprint 067 deliverable 5, AC5: the row counts equal what `/api/entries` returns
    for the same filters plus `key`/`value`."""
    app = create_app(settings(tmp_path))
    async with app.router.lifespan_context(app):
        repository = DomainRepository(app.state.engine)
        read = repository.create_or_get_entry(title="Read one", creators=("Cortázar",))
        wishlisted = repository.create_or_get_entry(title="Wishlisted one", creators=("Cortázar",))
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE entries SET status='read' WHERE id=:id"), {"id": read.entry_id}
            )
            connection.execute(
                text("UPDATE entries SET status='wishlist' WHERE id=:id"),
                {"id": wishlisted.entry_id},
            )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            unfiltered = await client.get(
                "/api/insights", params={"type": "book", "key": "creators", "metric": "count"}
            )
            filtered = await client.get(
                "/api/insights",
                params={
                    "type": "book",
                    "key": "creators",
                    "metric": "count",
                    "status": "read",
                },
            )
            entries = await client.get(
                "/api/entries",
                params={"type": "book", "status": "read", "key": "creators", "value": "cortazar"},
            )

    assert unfiltered.json()["rows"][0]["count"] == 2
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["rows"] == [
        {
            "key": "cortazar",
            "label": "Cortázar",
            "count": 1,
            "rated_count": 0,
            "mean_score": None,
            "score_spread": None,
            "covers": [],
        }
    ]
    assert filtered.json()["total_entries"] == 1
    assert entries.json()["total"] == filtered.json()["rows"][0]["count"]


@pytest.mark.anyio
async def test_an_invalid_status_filter_is_refused_as_entries_refuses_it(tmp_path: Path) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        insights = await client.get(
            "/api/insights",
            params={"type": "book", "key": "creators", "status": "not-a-real-status"},
        )
        entries = await client.get("/api/entries", params={"status": "not-a-real-status"})

    assert insights.status_code == entries.status_code == 422
