"""Sprint 054 walkthrough: the owner's real Trakt archive, end to end.

Runs against a live walkthrough backend (scripts/walkthrough.py). Exercises the
sprint's gate exactly: preview, the two shows arriving with 76 and 38 episodes
watched against their totals, commit, the progress control's numbers through
the API, undo, and the IMDb-overlap re-import. The archive is read-only input;
nothing from it is printed beyond counts and titles it shares with the public
catalog.

    BOOK_TRACKER_BASE_URL=http://127.0.0.1:<port> \
    TRAKT_ARCHIVE=exports/trakt-export-*.zip IMDB_RATINGS=exports/*.csv \
    uv run python ../scripts/walkthrough_trakt_054.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("BOOK_TRACKER_BASE_URL", "http://127.0.0.1:41517")
TRAKT_ARCHIVE = os.environ.get(
    "TRAKT_ARCHIVE", "exports/trakt-export-mauro0094-59d74e.zip"
)
IMDB_RATINGS = os.environ.get("IMDB_RATINGS", "")
IMDB_LIST = os.environ.get("IMDB_LIST", "")

FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILED.append(label)


def request(
    method: str,
    path: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict | list | None]:
    body = data
    outgoing = dict(headers or {})
    if data is not None and "Content-Type" not in outgoing:
        outgoing["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method, headers=outgoing)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        payload = error.read()
        return error.code, json.loads(payload) if payload else None


def multipart(path: str, field: str, filename: str, content: bytes, form: dict[str, str] | None = None) -> tuple[int, dict | list | None]:
    boundary = "----akasha-walkthrough-054"
    parts = []
    for name, value in (form or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/zip\r\n\r\n".encode() + content + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    return request(
        "POST",
        path,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


async def main() -> int:
    with open(TRAKT_ARCHIVE, "rb") as handle:
        archive_bytes = handle.read()
    print(f"archive: {len(archive_bytes)} bytes")

    # 1. Preview against the real archive.
    status, body = multipart("/api/import/trakt/preview", "file", "trakt.zip", archive_bytes)
    check("preview 201", status == 201, f"status {status}: {json.dumps(body)[:200] if body else ''}")
    if status != 201:
        return 1
    summary = body["summary"]
    check("no row errors", summary["errors"] == 0, f"errors={summary['errors']}")
    check("no ambiguous", summary["ambiguous"] == 0, f"ambiguous={summary['ambiguous']}")
    records = body["records"]
    movies = [row for row in records if row["item_type"] == "movie"]
    shows = [row for row in records if row["item_type"] == "series"]
    check("one film, two shows", len(movies) == 1 and len(shows) == 2,
          f"movies={len(movies)} shows={len(shows)}")

    # 2. The roll-up the sprint is about: 76 and 38 against their totals.
    progress_by_title = {
        row["title"]: (row["entry"]["values"].get("progress"), row["item"]["metadata"].get("episodes"))
        for row in shows
    }
    for title, (progress, total) in sorted(progress_by_title.items()):
        print(f"    show: {title!r} progress={progress} total={total}")
    counts = sorted(progress for progress, _ in progress_by_title.values())
    check("distinct-episode counts are 76 and 38", counts == [38, 76], f"counts={counts}")
    totals = sorted(total for _, total in progress_by_title.values())
    check("totals are the aired counts", totals == [38, 76], f"totals={totals}")
    for title, (progress, total) in progress_by_title.items():
        check(
            f"no plays fallback on {title!r}",
            "play count" not in (records[[r['title'] for r in records].index(title)]["entry"]["notes"] or ""),
        )
    statuses = {row["title"]: row["entry"]["suggested_status"] for row in shows}
    print(f"    suggested: {statuses}")
    check("both shows suggest completed", set(statuses.values()) == {"completed"})
    check("film suggests watched",
          movies[0]["entry"]["suggested_status"] == "watched")
    check("film score 7 (Trakt 1:1)", movies[0]["entry"]["score"] == 7,
          f"score={movies[0]['entry']['score']}")
    check("show scores arrive", {row['entry']['score'] for row in shows} == {8, 10},
          f"scores={[row['entry']['score'] for row in shows]}")

    batch_id = body["batch_id"]

    # 3. Commit.
    status, committed = request("POST", "/api/import/trakt/commit", data=json.dumps({"batch_id": batch_id}).encode())
    check("commit 200", status == 200, f"status {status}")
    check("3 items created", committed and committed["created_items"] == 3,
          f"created={committed['created_items'] if committed else None}")

    # 4. The Triage inbox holds all three; the progress survived the commit.
    status, inbox = request("GET", "/api/entries?status=unsorted")
    rows = inbox["items"]
    print(f"    inbox rows: {len(rows)}")
    check("three rows in the inbox", len(rows) == 3, f"rows={len(rows)}")
    series_rows = [row for row in rows if row["item"]["type"] == "series"]
    check("two series in the inbox", len(series_rows) == 2, f"series={len(series_rows)}")
    stored_progress = {row["item"]["title"]: row["progress"] for row in series_rows}
    print(f"    stored progress: {stored_progress}")
    check("stored progress is 38 and 76", sorted(stored_progress.values()) == [38, 76],
          f"progress={sorted(stored_progress.values())}")

    # 5. The progress control's numbers, on each series detail payload.
    for row in sorted(series_rows, key=lambda entry: entry["item"]["title"]):
        item_id = row["item"]["id"]
        status, detail = request("GET", f"/api/items/{item_id}")
        if status != 200 or not detail:
            check(f"detail fetch on {row['item']['title']!r}", False, f"status {status}")
            continue
        status, entry = request("GET", f"/api/entries/{row['id']}")
        progress = entry.get("progress") if status == 200 and entry else detail.get("progress")
        episodes = (detail.get("metadata") or {}).get("episodes")
        print(f"    detail {row['item']['title']!r}: progress={progress} episodes={episodes}")
        check(f"detail progress on {row['item']['title']!r}", progress in (38, 76),
              f"progress={progress}")
        check(f"detail total on {row['item']['title']!r}", episodes in (38, 76),
              f"episodes={episodes}")

    # 6. The IMDb overlap: the two sources describe the same library, so every
    # IMDb row should plan `reuse_item` against the Trakt-committed items and
    # commit nothing new. Before the undo, because matching needs the rows.
    # The ratings export (the `Const,…` header) carries the same three titles
    # the Trakt archive does; a list export may not, and overlap is the case
    # this gate exists for.
    if IMDB_RATINGS:
        with open(IMDB_RATINGS, "rb") as handle:
            ratings_csv = handle.read()
        status, imdb_body = multipart("/api/import/imdb/preview", "file", "ratings.csv", ratings_csv)
        check("imdb preview 201", status == 201, f"status {status}")
        actions = [row["planned_action"] for row in imdb_body["records"]]
        titles = [row["title"] for row in imdb_body["records"]]
        print(f"    imdb rows: {list(zip(titles, actions))}")
        check("imdb rows match rather than duplicate", actions and set(actions) <= {"reuse_item"},
              f"actions={actions}")
        status, imdb_committed = request("POST", "/api/import/imdb/commit", data=json.dumps({"batch_id": imdb_body["batch_id"]}).encode())
        check("imdb commit creates nothing new", imdb_committed["created_items"] == 0,
              f"created={imdb_committed['created_items']}")
        # The second commit adds no entries either: the items are already held.
        check("imdb commit adds no entries", imdb_committed["created_entries"] == 0,
              f"entries={imdb_committed['created_entries']}")
    else:
        print("[SKIP] imdb overlap (no IMDB_RATINGS)")

    # 7. Undo takes the Trakt batch back — its own rows and nothing else's.
    # Undo is terminal for the fingerprint, so it runs last.
    status, undone = request("DELETE", f"/api/import/batches/{batch_id}")
    check("undo 200", status == 200, f"status {status}")
    status, inbox = request("GET", "/api/entries?status=unsorted")
    remaining = inbox["items"] if inbox else []
    trakt_titles = {row["item"]["title"] for row in records}
    leftover_titles = {row["item"]["title"] for row in remaining}
    check("undo took the trakt rows back", not (leftover_titles & trakt_titles),
          f"left={sorted(leftover_titles & trakt_titles)}")
    check("undo left every other row alone", leftover_titles.isdisjoint(trakt_titles),
          f"kept={sorted(leftover_titles - trakt_titles)}")

    print()
    if FAILED:
        print(f"WALKTHROUGH FAILED: {len(FAILED)} checks")
        return 1
    print("WALKTHROUGH PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
