import ast
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

from alembic import command

# A version file declares its identity and its predecessor as plain module-level
# assignments, either bare or ``Literal[...]``-annotated. The chain is read from the
# files themselves rather than enumerated by hand, so the pending-list tests drift
# neither from Alembic nor from one another every time head moves.


def alembic_source_root() -> Path:
    """The repository root that owns ``alembic/``, with the same rule Alembic uses."""
    working_root = Path.cwd()
    return (
        working_root if (working_root / "alembic").is_dir() else Path(__file__).resolve().parents[2]
    )


def alembic_config(database_url: str) -> Config:
    root = alembic_source_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def _read_version_identifiers(path: Path) -> tuple[str, str | None]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    revision: str | None = None
    down_revision_sentinel = object()
    down_revision: str | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            value = _assignment_value(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            names = {node.target.id}
            value = _assignment_value(node.value)
        else:
            continue
        if "revision" in names:
            revision = _expect_string(value, path)
        if "down_revision" in names:
            down_revision_sentinel = None
            down_revision = _expect_optional_string(value, path)
    if revision is None:
        raise ValueError(f"{path.name} declares no module-level `revision` assignment")
    if down_revision_sentinel is not None:
        raise ValueError(f"{path.name} declares no `down_revision` assignment")
    return revision, down_revision


def _assignment_value(value: ast.expr) -> object:
    if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant):
        return value.slice.value
    if isinstance(value, ast.Constant):
        return value.value
    return None


def _expect_string(value: object, path: Path) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path.name}'s value must be a non-empty string literal")
    return value


def _expect_optional_string(value: object, path: Path) -> str | None:
    if value is None:
        return None
    return _expect_string(value, path)


def revision_chain_from_files(script_location: str | Path | None = None) -> list[str]:
    """The full migration chain, oldest first, without touching a database.

    Reads ``revision``/``down_revision`` straight out of the version files, the way
    Alembic itself builds the graph. The pending-list tests compare a database's
    outstanding work against the files here, never against a hand-maintained copy,
    so head moving is not a test edit. Raises on anything Alembic would refuse:
    duplicate revisions, a chain with more than one base, an orphan or a cycle.
    """
    root = Path(script_location) if script_location else alembic_source_root()
    versions_dir = root / "alembic" / "versions"
    links: dict[str, str | None] = {}
    for path in sorted(versions_dir.glob("[0-9][0-9][0-9][0-9]_*.py")):
        revision, down_revision = _read_version_identifiers(path)
        if revision in links:
            raise ValueError(f"duplicate migration revision {revision!r} in {versions_dir}")
        links[revision] = down_revision
    if not links:
        raise ValueError(f"no migration versions found under {versions_dir}")

    bases = [revision for revision, parent in links.items() if parent is None]
    if len(bases) != 1:
        raise ValueError(
            f"migration graph under {versions_dir} must have exactly one base revision; "
            f"found {sorted(bases)}"
        )
    chain: list[str] = []
    current: str | None = bases[0]
    while current is not None:
        chain.append(current)
        current = next((rev for rev, parent in links.items() if parent == current), None)
    if len(chain) != len(links):
        orphaned = sorted(set(links) - set(chain))
        raise ValueError(
            f"migration graph under {versions_dir} has a revision off the main chain: {orphaned}"
        )
    return chain


def pending_revisions(database_url: str) -> list[str]:
    """Revisions between the database's current version and head, oldest first.

    Returns every revision for a database that has never been stamped, so a fresh
    file and an out-of-date one are distinguishable by the caller: only the second
    has anything worth backing up before the upgrade runs.
    """
    config = alembic_config(database_url)
    script = ScriptDirectory.from_config(config)
    engine = create_engine(database_url)
    try:
        if "alembic_version" not in inspect(engine).get_table_names():
            current = None
        else:
            with engine.connect() as connection:
                current = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
    finally:
        engine.dispose()
    head = script.get_current_head()
    if head is None or current == head:
        return []
    return [revision.revision for revision in script.iterate_revisions(head, current)][::-1]


def schema_is_current(engine: Engine) -> bool:
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return False
    config = alembic_config(str(engine.url))
    with engine.connect() as connection:
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    head: str | None = ScriptDirectory.from_config(config).get_current_head()
    return bool(current == head)
