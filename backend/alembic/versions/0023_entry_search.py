"""Library search over every creator, series, subject and note (Sprint 089).

One FTS5 row per entry, `rowid` = `entries.id`, because the note being searched is the
entry's own and belongs to one person; the item's fields are copied into each of its
entries' rows. Triggers keep it current: an entry's insert, note change or delete, and an
item's title or metadata change. `unicode61 remove_diacritics 2` folds case and accents in
the index itself, so "cortazar" finds "Cortázar" with no Python function inside SQLite.

Arrays (creators, subjects) and strings are read through `json_each`, decoded, and
space-joined (see `_values`).
"""

from alembic import op

revision = "0023_entry_search"
down_revision = "0022_import_proposals"
branch_labels = None
depends_on = None


def _values(*keys: str) -> str:
    """Every value under these metadata keys, decoded and space-joined.

    `json_each` rather than `json_extract`: an array comes back from `json_extract` as
    its stored JSON text, and text written by `json.dumps` defaults escapes "á" to
    `\\u00e1`, which the tokenizer cannot fold. `json_each` yields decoded values,
    and one row for a plain string, so a scalar and a list read the same way.
    """
    parts = [
        f"coalesce((SELECT group_concat(value, ' ') FROM json_each(i.metadata, '$.{key}')), '')"
        for key in keys
    ]
    return " || ' ' || ".join(parts)


_ROW = f"""
SELECT e.id,
       coalesce(i.title, '') || ' ' || coalesce(i.subtitle, '') || ' '
         || {_values("original_title")},
       {_values("creators", "cast")},
       {_values("series")},
       {_values("subjects", "genres")},
       coalesce(e.notes, '')
FROM entries e JOIN items i ON i.id = e.item_id
"""

_INSERT = "INSERT INTO entry_search (rowid, title, creators, series, subjects, notes) " + _ROW


def upgrade() -> None:
    op.execute(
        "CREATE VIRTUAL TABLE entry_search USING fts5("
        "title, creators, series, subjects, notes, "
        "tokenize = 'unicode61 remove_diacritics 2')"
    )
    op.execute(_INSERT)
    op.execute(
        "CREATE TRIGGER entry_search_insert AFTER INSERT ON entries BEGIN "
        + _INSERT
        + " WHERE e.id = NEW.id; END"
    )
    op.execute(
        "CREATE TRIGGER entry_search_update AFTER UPDATE OF notes, item_id ON entries BEGIN "
        "DELETE FROM entry_search WHERE rowid = OLD.id; " + _INSERT + " WHERE e.id = NEW.id; END"
    )
    op.execute(
        "CREATE TRIGGER entry_search_delete AFTER DELETE ON entries BEGIN "
        "DELETE FROM entry_search WHERE rowid = OLD.id; END"
    )
    op.execute(
        "CREATE TRIGGER entry_search_item AFTER UPDATE OF title, subtitle, metadata ON items "
        "BEGIN "
        "DELETE FROM entry_search WHERE rowid IN (SELECT id FROM entries WHERE item_id = NEW.id); "
        + _INSERT
        + " WHERE e.item_id = NEW.id; END"
    )


def downgrade() -> None:
    for trigger in (
        "entry_search_insert",
        "entry_search_update",
        "entry_search_delete",
        "entry_search_item",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.execute("DROP TABLE IF EXISTS entry_search")
