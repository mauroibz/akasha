#!/usr/bin/env python3
"""Validate repository planning/state invariants without third-party packages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs/agent/state.json"
REQUIRED_PATHS = (
    "AGENTS.md",
    "README.md",
    "docs/specs/product-spec.md",
    "docs/specs/technical-spec.md",
    "docs/sprints/ROADMAP.md",
    "docs/sprints/TEMPLATE.md",
    "docs/agent/WORKFLOW.md",
    "docs/agent/HANDOFF.md",
    "docs/agent/worklog.md",
    "docs/agent/state.json",
    "docs/decisions.md",
)
PROJECT_STATUSES = {"ready", "in_progress", "blocked", "complete"}
SPRINT_STATUSES = {"planned", "ready", "in_progress", "blocked", "completed"}
ACTIVE_STATUSES = {"ready", "in_progress", "blocked"}
# The last sprint on `docs/sprints/ROADMAP.md`. A project may only be marked complete when
# every sprint through this one is completed, which is what stops a session from declaring
# the plan finished early. Move it whenever the roadmap is extended, and record the move in
# the decision that extends it (DEC-035 moved it to 19, DEC-042 to 26, DEC-052 to 28,
# DEC-058 to 29, DEC-065 to 30, DEC-071 to 31, DEC-076 revised 31's scope without moving it,
# DEC-079 to 32, DEC-081 to 33, DEC-082 to 34, DEC-083 to 35, DEC-085 to 36,
# DEC-089 to 41, DEC-094 to 42, DEC-095's first Triage insertion to 43,
# DEC-096's owner-approved follow-up to 44, DEC-097's measured movie gate to 45, and
# DEC-098's provider-backed movie domain/importer line to 47, DEC-103's poster sprint to 48,
# and DEC-104/DEC-106's measured series domain and multi-domain import line to 53,
# and DEC-111's gate-optimization insertion to 54, and DEC-114's recorded-defects sprint
# to 55, and DEC-117's four-sprint deployment line to 59, and DEC-119's names sprint inserted
# before the line, pushing it to 60).
FINAL_SPRINT = 61
GENERATED_DIRECTORIES = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "dist", "node_modules"}
RECORDINGS_DIRECTORY = ROOT / "backend" / "tests" / "fixtures" / "providers"
LINK_RE = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
SPRINT_STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*([a-z_]+)", re.MULTILINE)
SPRINT_ID_RE = re.compile(r"^(\d{3})-")


def load_json(path: Path, errors: list[str]) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot load {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)} must contain a JSON object")
        return {}
    return value


def sprint_status(path: Path, errors: list[str]) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return None
    match = SPRINT_STATUS_RE.search(text)
    if not match:
        errors.append(f"{path.relative_to(ROOT)} has no '**Status:** value")
        return None
    status = match.group(1)
    if status not in SPRINT_STATUSES:
        errors.append(f"{path.relative_to(ROOT)} has invalid sprint status {status!r}")
    return status


def validate_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_PATHS:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing required file: {relative}")
        elif path.stat().st_size == 0:
            errors.append(f"required file is empty: {relative}")


def validate_state(errors: list[str]) -> None:
    state = load_json(STATE_PATH, errors)
    if not state:
        return

    required_keys = {
        "schema_version",
        "plan_revision",
        "project_status",
        "active_sprint",
        "active_sprint_file",
        "active_sprint_status",
        "last_completed_sprint",
        "completed_sprints",
        "started_at",
        "updated_at",
    }
    missing = sorted(required_keys - state.keys())
    if missing:
        errors.append(f"state.json missing keys: {', '.join(missing)}")

    if state.get("schema_version") != 1:
        errors.append("state.json schema_version must be 1")
    plan_revision = state.get("plan_revision")
    if not isinstance(plan_revision, int) or plan_revision < 1:
        errors.append("state.json plan_revision must be a positive integer")

    project_status = state.get("project_status")
    if project_status not in PROJECT_STATUSES:
        errors.append(f"invalid project_status: {project_status!r}")

    completed = state.get("completed_sprints")
    if not isinstance(completed, list) or any(
        not isinstance(item, str) or not re.fullmatch(r"\d{3}", item) for item in completed
    ):
        errors.append("completed_sprints must be an array of three-digit strings")
        completed = []
    elif len(completed) != len(set(completed)):
        errors.append("completed_sprints contains duplicates")

    detailed_sprints: dict[str, tuple[Path, str | None]] = {}
    for path in sorted((ROOT / "docs/sprints").glob("[0-9][0-9][0-9]-*.md")):
        match = SPRINT_ID_RE.match(path.name)
        assert match is not None
        sprint_id = match.group(1)
        if sprint_id in detailed_sprints:
            errors.append(f"multiple detailed sprint files for {sprint_id}")
        detailed_sprints[sprint_id] = (path, sprint_status(path, errors))

    if project_status == "complete":
        if state.get("active_sprint") is not None or state.get("active_sprint_file") is not None:
            errors.append("complete project must have null active sprint and file")
        if state.get("active_sprint_status") is not None:
            errors.append("complete project must have null active_sprint_status")
        expected_all = [f"{number:03d}" for number in range(1, FINAL_SPRINT + 1)]
        if completed != expected_all:
            errors.append(
                f"complete project must list completed_sprints 001 through {FINAL_SPRINT:03d} in order"
            )
    else:
        active_id = state.get("active_sprint")
        active_file_value = state.get("active_sprint_file")
        active_status = state.get("active_sprint_status")
        if not isinstance(active_id, str) or not re.fullmatch(r"\d{3}", active_id):
            errors.append("active_sprint must be a three-digit string")
        else:
            expected_active = f"{len(completed) + 1:03d}"
            if active_id != expected_active:
                errors.append(
                    f"active_sprint must follow completed_sprints sequentially ({expected_active})"
                )
        if active_status not in ACTIVE_STATUSES:
            errors.append(f"active_sprint_status must be one of {sorted(ACTIVE_STATUSES)}")
        if project_status != active_status:
            errors.append("project_status must match active_sprint_status while work remains")
        if not isinstance(active_file_value, str):
            errors.append("active_sprint_file must be a repository-relative string")
        else:
            active_path = (ROOT / active_file_value).resolve()
            try:
                active_path.relative_to(ROOT.resolve())
            except ValueError:
                errors.append("active_sprint_file escapes repository root")
            else:
                if not active_path.is_file():
                    errors.append(f"active sprint file does not exist: {active_file_value}")
                else:
                    file_match = SPRINT_ID_RE.match(active_path.name)
                    if file_match is None or file_match.group(1) != active_id:
                        errors.append("active_sprint does not match active_sprint_file name")
                    file_status = sprint_status(active_path, errors)
                    if file_status != active_status:
                        errors.append(
                            "active_sprint_status does not match status in active sprint file "
                            f"({active_status!r} != {file_status!r})"
                        )

        active_files = [
            (sprint_id, path, status)
            for sprint_id, (path, status) in detailed_sprints.items()
            if status in ACTIVE_STATUSES
        ]
        if len(active_files) != 1:
            errors.append(
                f"expected exactly one detailed active sprint file, found {len(active_files)}"
            )
        elif active_files[0][0] != active_id:
            errors.append("active detailed sprint file does not match state active_sprint")

    for sprint_id in completed:
        sprint = detailed_sprints.get(sprint_id)
        if sprint is None:
            errors.append(f"completed sprint {sprint_id} has no detailed sprint file")
        elif sprint[1] != "completed":
            errors.append(f"completed sprint {sprint_id} file status is {sprint[1]!r}")

    file_completed = {
        sprint_id for sprint_id, (_, status) in detailed_sprints.items() if status == "completed"
    }
    if file_completed != set(completed):
        errors.append(
            "completed_sprints differs from completed detailed files: "
            f"state={sorted(completed)}, files={sorted(file_completed)}"
        )

    expected_last = completed[-1] if completed else None
    if state.get("last_completed_sprint") != expected_last:
        errors.append(
            f"last_completed_sprint must be {expected_last!r} based on completed_sprints order"
        )

    roadmap = ROOT / "docs/sprints/ROADMAP.md"
    if roadmap.is_file() and project_status != "complete":
        roadmap_text = roadmap.read_text(encoding="utf-8")
        active_file_value = state.get("active_sprint_file")
        if isinstance(active_file_value, str):
            basename = Path(active_file_value).name
            if basename not in roadmap_text:
                errors.append(f"ROADMAP.md does not reference active sprint file {basename}")


def validate_markdown_links(errors: list[str]) -> None:
    for path in sorted(ROOT.rglob("*.md")):
        if any(part in GENERATED_DIRECTORIES for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            target = unquote(target.split("#", 1)[0])
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{path.relative_to(ROOT)} has link escaping root: {raw_target}")
                continue
            if not resolved.exists():
                errors.append(
                    f"{path.relative_to(ROOT)} has broken local link: {raw_target}"
                )


def validate_text_hygiene(errors: list[str]) -> None:
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in GENERATED_DIRECTORIES for part in path.parts):
            continue
        if RECORDINGS_DIRECTORY in path.parents:
            # Recorded provider responses are byte-faithful captures of what a live
            # provider actually sent (DEC-025). Reformatting them would quietly change
            # what the regression tests assert against.
            continue
        if path.suffix not in {".md", ".json", ".py", ".yml", ".yaml", ".toml"} and path.name not in {
            ".gitignore",
            ".editorconfig",
            "Makefile",
        }:
            continue
        data = path.read_bytes()
        if b"\r\n" in data:
            errors.append(f"{path.relative_to(ROOT)} contains CRLF line endings")
        if data and not data.endswith(b"\n"):
            errors.append(f"{path.relative_to(ROOT)} has no trailing newline")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    if STATE_PATH.is_file():
        validate_state(errors)
    validate_markdown_links(errors)
    validate_text_hygiene(errors)

    if errors:
        print("Project validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("Project validation passed: required docs, sprint state, links, and text hygiene are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
