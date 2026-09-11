"""The version-surface check DEC-145 asked for, proven by failure as well as success.

The four surfaces — ``backend/pyproject.toml``, ``frontend/package.json``, the
FastAPI ``version=`` in ``backend/src/book_tracker/main.py`` and the committed
``frontend/openapi.json`` — must agree. Until Sprint 082 nothing cheap enforced
that: the only check lived inside the minutes-long container smoke test, so a
bumped-but-not-regenerated contract could sit on a branch for days.

These tests import the validator and exercise its ``version_surfaces`` function
against temporary copies of the real files, so the assertions never depend on
which version the repository happens to carry today.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import validate_project as vp  # noqa: E402

WRITERS: dict[str, Callable[[Path, str], None]] = {}


def _writer(surface: str) -> Callable[[Callable[[Path, str], None]], Callable[[Path, str], None]]:
    def register(function: Callable[[Path, str], None]) -> Callable[[Path, str], None]:
        WRITERS[surface] = function
        return function

    return register


@_writer("backend/pyproject.toml")
def _write_pyproject(root: Path, version: str) -> None:
    path = root / "backend/pyproject.toml"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()]
    lines = [line for line in lines if not line.startswith("version = ")]
    for index, line in enumerate(lines):
        if line.startswith("[project]"):
            lines.insert(index + 1, f'version = "{version}"')
            break
    else:  # pragma: no cover - the real file always has a [project] table
        raise AssertionError("pyproject.toml has no [project] table")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@_writer("frontend/package.json")
def _write_package(root: Path, version: str) -> None:
    path = root / "frontend/package.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["version"] = version
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


@_writer("frontend/openapi.json")
def _write_contract(root: Path, version: str) -> None:
    path = root / "frontend/openapi.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["info"]["version"] = version
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


@_writer("backend/src/book_tracker/main.py")
def _write_fastapi(root: Path, version: str) -> None:
    path = root / "backend/src/book_tracker/main.py"
    text = path.read_text(encoding="utf-8")
    assert 'version="' in text
    start = text.index('version="')
    end = start + len('version="') + text[start + len('version="') :].index('"')
    path.write_text(text[:start] + f'version="{version}"' + text[end:], encoding="utf-8")


SURFACE_PATHS = tuple(WRITERS)


@pytest.fixture()
def surfaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the repository's four version surfaces in a throwaway root."""
    for relative in SURFACE_PATHS:
        source = REPO_ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, target)
    monkeypatch.setattr(vp, "ROOT", tmp_path)
    return tmp_path


def _errors(root: Path) -> list[str]:
    collected: list[str] = []
    vp.version_surfaces(root, collected)
    return collected


def _read(root: Path, *, surface: str = "backend/pyproject.toml") -> str:
    collected: list[str] = []
    version = vp.version_surfaces(root, collected)
    assert not collected, collected
    assert isinstance(version, str)
    return version


def test_the_repository_itself_agrees() -> None:
    assert not _errors(REPO_ROOT)


def test_agreeing_surfaces_report_the_version(surfaces: Path) -> None:
    version = _read(surfaces)
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[A-Za-z0-9.]+)?", version)
    assert version == _read(REPO_ROOT)


@pytest.mark.parametrize("surface", SURFACE_PATHS)
def test_one_disagreeing_surface_fails(surfaces: Path, surface: str) -> None:
    original = _read(surfaces)
    WRITERS[surface](surfaces, "9.9.9")
    errors = _errors(surfaces)
    assert errors, f"a disagreeing {surface} did not fail the check"
    assert any(surface in error for error in errors), errors
    WRITERS[surface](surfaces, original)
    assert not _errors(surfaces)


def test_a_missing_surface_fails(surfaces: Path) -> None:
    (surfaces / "frontend/openapi.json").unlink()
    assert _errors(surfaces)
