#!/usr/bin/env python3
"""Generate docs/agent/state.json from the detailed sprint files.

The sprint files under docs/sprints/ are the single source of truth for sprint
state (each carries a `**Status:** value` line). state.json used to be edited by
hand in parallel with them, and the two artifacts had to agree or the validator
failed the whole gate (DEC-148). This script makes state.json a generated file:
it reads every sprint file, derives the active sprint, the completed sequence
and the project status, and rewrites state.json so it always agrees with the
files.

Do not hand-edit state.json — run this script. The flip of a sprint's status
line (ready -> in_progress -> completed, etc.) can be done here too, so both
halves of a state change happen in one call that refuses illegal transitions:

    python scripts/sync_sprint_state.py                     # regenerate only
    python scripts/sync_sprint_state.py --sprint 076 in_progress
    python scripts/sync_sprint_state.py --sprint 076 completed --sprint 077 ready
    python scripts/sync_sprint_state.py --dry-run           # show, do not write

The project validator (scripts/validate_project.py) keeps its cross-checks as a
second independent guard: it verifies what this script produces rather than
trusting it.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_project import (  # noqa: E402
    ACTIVE_STATUSES,
    FINAL_SPRINT,
    SPRINT_ID_RE,
    SPRINT_STATUSES,
    SPRINT_STATUS_RE,
)

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs/agent/state.json"
SPRINTS_DIR = ROOT / "docs/sprints"

# The transition graph from docs/agent/WORKFLOW.md's state table, plus the
# closure edge: the active sprint completes from in_progress, and its successor
# is activated in the same call (or before it, in the --sprint pair). blocked ->
# completed covers a pivot where a blocked sprint closes without resuming. There
# is no edge out of `completed` (WORKFLOW's no completed -> in_progress rule).
TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"ready"}),
    "ready": frozenset({"in_progress", "blocked"}),
    "in_progress": frozenset({"completed", "blocked"}),
    "blocked": frozenset({"in_progress", "completed"}),
    "completed": frozenset(),
}


def fail(message: str) -> NoReturn:
    print(f"sync_sprint_state: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_state() -> dict[str, object]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {STATE_PATH.relative_to(ROOT)}: {exc}")


def scan_sprint_files(errors: list[str]) -> dict[str, tuple[Path, str]]:
    """Every detailed sprint file, keyed by its three-digit id, with its Status."""
    found: dict[str, tuple[Path, str]] = {}
    for path in sorted(SPRINTS_DIR.glob("[0-9][0-9][0-9]-*.md")):
        match = SPRINT_ID_RE.match(path.name)
        assert match is not None
        sprint_id = match.group(1)
        text = path.read_text(encoding="utf-8")
        status_match = SPRINT_STATUS_RE.search(text)
        if status_match is None:
            errors.append(f"{path.relative_to(ROOT)} has no '**Status:**' line")
            continue
        status = status_match.group(1)
        if status not in SPRINT_STATUSES:
            errors.append(f"{path.relative_to(ROOT)} has invalid sprint status {status!r}")
            continue
        if sprint_id in found:
            errors.append(f"duplicate detailed sprint files for {sprint_id}")
            continue
        found[sprint_id] = (path, status)
    return found


def derive_state(
    files: dict[str, tuple[Path, str]],
    plan_revision: int,
    started_at: str,
    errors: list[str],
    close_flip: bool = False,
) -> dict[str, object]:
    """The state.json content derived from the sprint files, without a timestamp.

    ``close_flip`` marks that a sprint is being completed in this call; the
    ritual (AGENTS.md §2.1/§5.2) owns ``started_at`` only for the sprint being
    implemented, so closing one clears it for the successor to set when it
    itself moves to ``in_progress``.
    """
    if close_flip:
        started_at = ""
    completed = sorted(sprint_id for sprint_id, (_, status) in files.items() if status == "completed")
    expected_completed = [f"{number:03d}" for number in range(1, len(completed) + 1)]
    if completed != expected_completed:
        gaps = sorted(set(expected_completed) - set(completed))
        errors.append(
            "completed sequence has a gap (a completed sprint is missing before the next one): "
            f"{', '.join(gaps)}"
        )

    actives: list[tuple[str, str]] = sorted(
        (sprint_id, status)
        for sprint_id, (_, status) in files.items()
        if status in ACTIVE_STATUSES
    )
    if len(actives) > 1:
        errors.append(
            f"exactly one sprint may be {'/'.join(sorted(ACTIVE_STATUSES))}; found "
            f"{', '.join(f'{sprint_id} ({status})' for sprint_id, status in actives)}"
        )

    project_status: str
    active_sprint: str | None = None
    active_file: str | None = None
    active_status: str | None = None

    if len(actives) == 1:
        sprint_id, status = actives[0]
        active_sprint, active_file, active_status = (
            sprint_id,
            str(files[sprint_id][0].relative_to(ROOT)),
            status,
        )
        project_status = status
        if completed:
            expected_active = f"{int(completed[-1]) + 1:03d}"
            if sprint_id != expected_active:
                errors.append(
                    f"active sprint {sprint_id} but the next one after {completed[-1]} would be "
                    f"{expected_active}"
                )
        elif sprint_id != "001":
            errors.append(f"active sprint {sprint_id} but no sprint is completed; expected 001")
    else:
        project_status = "complete"
        incomplete = sorted(
            sprint_id for sprint_id, (_, status) in files.items() if status != "completed"
        )
        if incomplete:
            errors.append(
                "project cannot be complete: sprint files are still open: "
                f"{', '.join(incomplete)}"
            )
        if len(completed) != FINAL_SPRINT:
            errors.append(
                f"FINAL_SPRINT in scripts/validate_project.py is {FINAL_SPRINT} but "
                f"{len(completed)} sprints are completed; move it with a decision entry first"
            )
        started_at = ""

    return {
        "schema_version": 1,
        "plan_revision": plan_revision,
        "project_status": project_status,
        "active_sprint": active_sprint,
        "active_sprint_file": active_file,
        "active_sprint_status": active_status,
        "last_completed_sprint": completed[-1] if completed else None,
        "completed_sprints": completed,
        "started_at": started_at,
    }


def agree(derived: dict[str, object], current: dict[str, object]) -> bool:
    """True when state.json matches the files, ignoring the updated_at timestamp."""
    return all(derived.get(key) == current.get(key) for key in derived if key != "updated_at")


def flip_status_text(text: str, old_status: str, new_status: str) -> str:
    """The sprint file's text with exactly its Status line changed."""
    match = SPRINT_STATUS_RE.search(text)
    assert match is not None and match.group(1) == old_status
    start, end = match.start(1), match.end(1)
    return text[:start] + new_status + text[end:]


def write_atomic(path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name)
    with open(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    Path(tmp_name).replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--sprint",
        nargs=2,
        action="append",
        metavar=("ID", "STATUS"),
        help="flip a sprint file's Status line, e.g. --sprint 076 in_progress",
    )
    parser.add_argument(
        "--plan-revision",
        type=int,
        default=None,
        help="bump plan_revision to this value (plan changes only; must exceed the current one)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    args = parser.parse_args()

    current_state = load_state()
    plan_revision = current_state.get("plan_revision")
    if not isinstance(plan_revision, int) or plan_revision < 1:
        fail(f"state.json plan_revision is not a positive integer: {plan_revision!r}")
    if args.plan_revision is not None:
        if args.plan_revision <= plan_revision:
            fail(f"--plan-revision {args.plan_revision} must exceed the current {plan_revision}")
        plan_revision = args.plan_revision

    errors: list[str] = []
    files = scan_sprint_files(errors)
    if errors:
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        fail("sprint files are in an inconsistent state; refusing to derive state from them")

    staged: dict[str, tuple[Path, str, str]] = {}  # id -> (path, old, new text)
    for sprint_id, new_status in args.sprint or []:
        if sprint_id not in files:
            fail(f"no detailed sprint file for {sprint_id}")
        if new_status not in SPRINT_STATUSES:
            fail(f"unknown status {new_status!r}; choose from {sorted(SPRINT_STATUSES)}")
        path, old_status = files[sprint_id]
        if new_status == old_status:
            fail(f"sprint {sprint_id} is already {new_status!r}")
        allowed = TRANSITIONS.get(old_status, frozenset())
        if new_status not in allowed:
            fail(
                f"illegal transition for {sprint_id}: {old_status} -> {new_status}; "
                f"allowed from {old_status}: {sorted(allowed) or 'none (terminal state)'}"
            )
        staged[sprint_id] = (path, old_status, flip_status_text(path.read_text(encoding="utf-8"), old_status, new_status))
        files[sprint_id] = (path, new_status)

    close_flip = any(files[sprint_id][1] == "completed" for sprint_id in staged)
    derived = derive_state(
        files,
        plan_revision,
        str(current_state.get("started_at") or ""),
        errors,
        close_flip=close_flip,
    )
    # The ritual (AGENTS.md §2.1) owns the timestamp of the sprint being
    # implemented: an in_progress flip sets it when empty; nothing overwrites it.
    progress_flip = any(files[sprint_id][1] == "in_progress" for sprint_id in staged)
    if progress_flip and not derived.get("started_at"):
        derived["started_at"] = datetime.now().astimezone().replace(microsecond=0).isoformat()
    if errors:
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        fail("the requested state change breaks the sprint invariants; nothing was written")

    if agree(derived, current_state) and not staged:
        print("state.json already agrees with the sprint files; nothing to do.")
        return 0

    for sprint_id, (path, _, _) in sorted(staged.items()):
        print(f"  flip {path.relative_to(ROOT)}: Status -> {files[sprint_id][1]}")
    changed_keys = sorted(key for key in derived if key != "updated_at" and derived[key] != current_state.get(key))
    print(f"  state.json: {', '.join(changed_keys) if changed_keys else 'nothing new beyond the timestamp'}")
    if args.dry_run:
        print("dry run — nothing written.")
        return 0

    for _, (path, _, new_text) in sorted(staged.items()):
        write_atomic(path, new_text)
    full_state = {
        **derived,
        "updated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }
    write_atomic(STATE_PATH, json.dumps(full_state, indent=2, ensure_ascii=False) + "\n")
    print("sprint files and state.json agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
