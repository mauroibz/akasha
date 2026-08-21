"""The flat-entry contract, guarded.

DEC-077's verdict is that a child of an entry needs no state of its own — depth is a
per-domain `progress` field or a marker in provider `rows`, never a child entity.
That verdict is only as good as the contract staying flat, so this test watches the
one place a child entity would have to appear: a parent pointer on `entries`. If a
future sprint legitimately adds one, it must come through DEC-077's reopen
conditions, and this test failing is how it announces itself.
"""

from book_tracker.infrastructure.models import EntryRow


def test_an_entry_has_no_parent() -> None:
    columns = set(EntryRow.__table__.columns.keys())

    assert "parent_entry_id" not in columns
    assert "parent_id" not in columns
    # Belt and braces: no column whose name is a parent pointer under another
    # spelling, and no self-referencing foreign key.
    assert not any(name.startswith("parent") for name in columns)
    self_refs = [
        fk
        for column in EntryRow.__table__.columns
        for fk in column.foreign_keys
        if fk.column.table.name == "entries"
    ]
    assert self_refs == []
