"""The pile, ranked (Sprint 132, DEC-183 point 3, DEC-186).

What waiting entry is the person most likely to want next? Each one is scored from
signals the library already holds, and each signal that fired leaves a short sentence
naming its evidence. Nothing here asks a provider: the ranking is a handful of
queries over stored rows.

Signals, each a number of points (the weights are below, in one place):

- **series**: the next one in a series the person is under way in or has finished,
  scaled by the scores they gave it;
- **creator**: the person's mean score for the creator above their own average for
  that library, shrunk while the count is small;
- **affinity**: the same for a subject or genre (`RankingSpec.affinity_fields`), with
  recent scores counting for more than old ones;
- **waiting**: a little per year on the pile, so the old pile surfaces slowly;
- **goal**: a library short of its goal's pace is lifted, across libraries only;
- **set_aside**: something started and put back lately is pushed down;
- **similarity**: with embeddings configured (Sprint 136), what stands closest to the
  person's highest scores in that library, against the rest of the pile, names the
  scored work it is closest to.

Ties break on entry id, so the same library always gives the same order.

Shared layer: no domain, status or field is named here. Which statuses are the pile,
under way, finished or abandoned comes from `StatusSpec`; which fields carry a series
or a taste comes from the domain's `RankingSpec`.
"""

import re
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from book_tracker.application.embeddings import centroid, load_vectors, similarity
from book_tracker.domain.normalization import normalize_text
from book_tracker.domain.registry import DOMAINS
from book_tracker.domain.spec import Domain

# --- Weights: every number the order depends on --------------------------------------

#: The next in a series, at a mean score of `SERIES_FULL_AT` (more lifts up to 1.25x).
SERIES_WEIGHT = 3.0
SERIES_FULL_AT = 8.0
#: The next after one still under way waits a little behind one ready to start.
SERIES_UNDER_WAY = 0.5
#: A series whose scores average below this is not pushed.
SERIES_MIN_MEAN = 6.0
#: Points per score point a creator stands above the person's mean, before shrinking.
CREATOR_WEIGHT = 1.5
#: Rated entries a creator needs; the shrink is n / (n + CREATOR_SHRINK).
CREATOR_MIN_RATED = 2
CREATOR_SHRINK = 2.0
CREATOR_CAP = 3.0
#: Points per (recency-weighted) score point a subject stands above the mean.
AFFINITY_WEIGHT = 1.5
AFFINITY_MIN_RATED = 3
#: Weight units added to the denominator, so three recent scores are not a certainty.
AFFINITY_SHRINK = 2.0
#: A score's weight halves every this many years, and never falls below the floor:
#: an old love still counts, a quarter as much.
AFFINITY_HALF_LIFE_YEARS = 2.0
AFFINITY_FLOOR = 0.25
#: Below this many points a subject is not a reason.
AFFINITY_MIN_LIFT = 0.1
AFFINITY_CAP = 2.0
#: A subject on more than this share of a library's scored entries is not a taste.
AFFINITY_MAX_SHARE = 0.5
#: Points per year on the pile, up to the cap: small on purpose.
WAITING_PER_YEAR = 0.15
WAITING_CAP_YEARS = 5.0
#: The most a library short of its goal's pace is lifted (a month's pace short or more).
GOAL_WEIGHT = 0.75
#: How far down something set aside today goes; it fades to nothing over the window.
SET_ASIDE_WEIGHT = 2.0
SET_ASIDE_DAYS = 90
#: Points for the waiting entry closest to the person's best-scored, with embeddings
#: configured. Measured against the pile itself, not a fixed cosine, because each
#: model spreads its similarities differently: the closest gets all of it, one at
#: the pile's median none.
SIMILARITY_WEIGHT = 2.0
#: Below this share of the way from the median to the closest, nothing is close.
SIMILARITY_MIN_LIFT = 0.34
#: The highest scores above the person's mean a library is compared with.
SIMILARITY_LIKED = 10
#: With fewer waiting entries embedded, "closer than the rest" says nothing.
SIMILARITY_MIN_PILE = 3
#: At most this many entries in a library are lifted and named.
SIMILARITY_TOP = 50

#: "Mistborn #2", "Mistborn, #2", "Mistborn (2)".
_POSITION_IN_VALUE = re.compile(r"^(?P<name>.*?)[\s,]*(?:#\s*|\(\s*)(?P<pos>\d+(?:\.\d+)?)\)?\s*$")
#: "The Final Empire (Mistborn, #1)", as a Goodreads export writes a title.
_SERIES_IN_TITLE = re.compile(r"\((?P<name>[^()]*?),?\s*#(?P<pos>\d+(?:\.\d+)?)\)\s*$")


@dataclass
class _Candidate:
    entry_id: int
    item_type: str
    title: str
    creator: str | None
    creator_key: str | None
    date_added: str | None
    date_started: str | None
    updated_at: str | None
    series_value: Any
    item_id: int | None = None
    signals: list[tuple[str, float, str]] = field(default_factory=list)

    @property
    def score(self) -> float:
        return sum(points for _signal, points, _text in self.signals)


@dataclass
class _SeriesMember:
    entry_id: int
    status: str
    score: int | None
    title: str
    position: float | None
    finished_on: str | None
    updated_at: str | None


@dataclass
class _Taste:
    """One subject's scores: how many, their sum, and their recency-weighted sums."""

    name: str
    rated: int = 0
    total: float = 0.0
    #: Recency-weighted: the sum of weight times score, and of the weights.
    weighted: float = 0.0
    weight: float = 0.0


def rank_pile(
    engine: Engine,
    user_id: int,
    item_type: str | None,
    limit: int,
    *,
    today: date | None = None,
    embedding_model: str | None = None,
) -> list[dict[str, Any]]:
    """The `limit` waiting entries most likely wanted next, best first.

    Each is `{"entry_id", "score", "reasons": [{"signal", "text"}]}`; reasons are the
    signals that fired, the strongest first. `item_type=None` ranks every library's
    pile together, and only then does a goal's pace count. `embedding_model` is the
    configured endpoint's: only then are stored vectors read (Sprint 136), so without
    it the order is Sprint 132's exactly.
    """
    today = today or datetime.now(UTC).date()
    domains = [
        domain
        for domain in DOMAINS.values()
        if (item_type is None or domain.item_type == item_type) and _planned(domain)
    ]
    if not domains or limit < 1:
        return []
    with engine.connect() as connection:
        candidates = _candidates(connection, user_id, domains)
        if not candidates:
            return []
        _creator_signal(connection, user_id, domains, candidates)
        _series_signal(connection, user_id, domains, candidates)
        _affinity_signal(connection, user_id, domains, candidates, today)
        if item_type is None:
            _goal_signal(connection, user_id, domains, candidates, today)
        if embedding_model is not None:
            _similarity_signal(connection, user_id, domains, candidates, embedding_model)
    for candidate in candidates:
        _waiting_signal(candidate, today)
        _set_aside_signal(candidate, today)
    ranked = _in_rounds(sorted(candidates, key=lambda c: (-round(c.score, 6), c.entry_id)))[:limit]
    return [
        {
            "entry_id": candidate.entry_id,
            "score": round(candidate.score, 2),
            "reasons": [
                {"signal": signal, "text": reason}
                for signal, _points, reason in sorted(candidate.signals, key=lambda s: -abs(s[1]))
            ],
        }
        for candidate in ranked
    ]


def _in_rounds(ranked: list[_Candidate]) -> list[_Candidate]:
    """Every creator's best before any creator's second (DEC-192).

    The scores stand; only the order changes, so one prolific creator cannot fill the top
    of the pile. Within a creator the score's order holds. An entry without a creator is
    a creator of its own.
    """
    seen: dict[tuple[str, str], int] = defaultdict(int)
    rounds: list[int] = []
    for candidate in ranked:
        if candidate.creator_key:
            key = (candidate.item_type, candidate.creator_key)
            rounds.append(seen[key])
            seen[key] += 1
        else:
            rounds.append(0)
    order = sorted(range(len(ranked)), key=lambda index: (rounds[index], index))
    return [ranked[index] for index in order]


def _planned(domain: Domain) -> list[str]:
    return [status.value for status in domain.statuses if status.planned]


def _in(prefix: str, values: Sequence[str], params: dict[str, Any]) -> str:
    """`:prefix0, :prefix1, ...` for an IN list, the values added to `params`."""
    for index, value in enumerate(values):
        params[f"{prefix}{index}"] = value
    return ", ".join(f":{prefix}{index}" for index in range(len(values)))


def _candidates(connection: Connection, user_id: int, domains: list[Domain]) -> list[_Candidate]:
    """Every waiting entry in these domains, with what the signals read of it."""
    params: dict[str, Any] = {"user": user_id}
    pile = {(domain.item_type, value) for domain in domains for value in _planned(domain)}
    statuses = _in("s", sorted({value for _type, value in pile}), params)
    series_cases = []
    for index, domain in enumerate(domains):
        if domain.ranking.series_field:
            params[f"type{index}"] = domain.item_type
            params[f"series{index}"] = f"$.{domain.ranking.series_field}"
            series_cases.append(f"WHEN :type{index} THEN json_extract(i.metadata, :series{index})")
    series = f"CASE i.type {' '.join(series_cases)} END" if series_cases else "NULL"
    # The status index finds the pile; a status two domains share is sorted out here.
    rows = connection.execute(
        text(
            "SELECT e.status, e.id, i.type, i.title, i.creator_primary,"
            " i.creator_primary_normalized, e.date_added, e.date_started, e.updated_at,"
            f" {series}, e.item_id FROM entries e JOIN items i ON i.id = e.item_id"
            f" WHERE e.user_id = :user AND e.status IN ({statuses})"
        ),
        params,
    ).all()
    return [_Candidate(*row[1:]) for row in rows if (row[2], row[0]) in pile]


def _creator_signal(
    connection: Connection, user_id: int, domains: list[Domain], candidates: list[_Candidate]
) -> None:
    """Lift a creator the person rates above their own average in that library.

    One pass over the scored entries gives both: per creator, and summed per library,
    the mean "above your average" is measured from.
    """
    params: dict[str, Any] = {"user": user_id}
    types = _in("t", [domain.item_type for domain in domains], params)
    rows = connection.execute(
        text(
            "SELECT i.type, i.creator_primary_normalized, sum(e.score), count(*)"
            " FROM entries e JOIN items i ON i.id = e.item_id"
            f" WHERE e.user_id = :user AND i.type IN ({types}) AND e.score IS NOT NULL"
            " GROUP BY 1, 2"
        ),
        params,
    ).all()
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    rated: dict[tuple[str, str], tuple[float, int]] = {}
    for item_type, key, total, count in rows:
        totals[item_type][0] += total
        totals[item_type][1] += count
        if key is not None and count >= CREATOR_MIN_RATED:
            rated[(item_type, key)] = (total / count, count)
    means = {item_type: total / count for item_type, (total, count) in totals.items()}
    for candidate in candidates:
        found = rated.get((candidate.item_type, candidate.creator_key or ""))
        if found is None or candidate.creator is None:
            continue
        mean, count = found
        lift = (mean - means[candidate.item_type]) * count / (count + CREATOR_SHRINK)
        if lift <= 0:
            continue
        points = min(CREATOR_CAP, CREATOR_WEIGHT * lift)
        candidate.signals.append(
            ("creator", points, f"You rate {candidate.creator} {mean:.1f} across {count}")
        )


def _series_of(domain: Domain, title: str, value: Any) -> tuple[str, str, float | None] | None:
    """`(key, name, position)` for a work's series, or `None` when it names none."""
    if isinstance(value, str) and value.strip():
        match = _POSITION_IN_VALUE.match(value.strip())
        name, position = (
            (match["name"].strip(), float(match["pos"]))
            if match and match["name"].strip()
            else (value.strip(), None)
        )
        if position is None and domain.ranking.series_in_title:
            in_title = _SERIES_IN_TITLE.search(title or "")
            if in_title and normalize_text(in_title["name"]) == normalize_text(name):
                position = float(in_title["pos"])
        return normalize_text(name), name, position
    if domain.ranking.series_in_title:
        in_title = _SERIES_IN_TITLE.search(title or "")
        if in_title and in_title["name"].strip():
            name = in_title["name"].strip()
            return normalize_text(name), name, float(in_title["pos"])
    return None


def _place(domain: Domain, position: float) -> str:
    number = int(position) if position.is_integer() else position
    return f"{domain.label.lower()} {number}"


def _series_signal(
    connection: Connection, user_id: int, domains: list[Domain], candidates: list[_Candidate]
) -> None:
    """Lift the next waiting entry of each series the person is under way in or finished."""
    with_series = [domain for domain in domains if domain.ranking.series_field]
    if not with_series:
        return
    by_type = {domain.item_type: domain for domain in with_series}
    # Only a waiting entry that names a series can be lifted; without one, nothing to read.
    if not any(
        candidate.item_type in by_type
        and _series_of(by_type[candidate.item_type], candidate.title, candidate.series_value)
        for candidate in candidates
    ):
        return
    params: dict[str, Any] = {"user": user_id}
    clauses = []
    for index, domain in enumerate(with_series):
        params[f"type{index}"] = domain.item_type
        params[f"field{index}"] = f"$.{domain.ranking.series_field}"
        named = f"json_extract(i.metadata, :field{index}) IS NOT NULL"
        if domain.ranking.series_in_title:
            named = f"({named} OR i.title LIKE '%#%)')"
        clauses.append(f"(i.type = :type{index} AND {named})")
    cases = " ".join(
        f"WHEN :type{index} THEN json_extract(i.metadata, :field{index})"
        for index in range(len(with_series))
    )
    rows = connection.execute(
        text(
            "SELECT e.id, i.type, e.status, e.score, i.title, e.date_finished, e.updated_at,"
            f" CASE i.type {cases} END FROM entries e JOIN items i ON i.id = e.item_id"
            f" WHERE e.user_id = :user AND ({' OR '.join(clauses)})"
        ),
        params,
    ).all()
    series: dict[tuple[str, str], list[_SeriesMember]] = defaultdict(list)
    names: dict[tuple[str, str], str] = {}
    for entry_id, item_type, status, score, title, finished_on, updated_at, value in rows:
        found = _series_of(by_type[item_type], title, value)
        if found is None:
            continue
        key, name, position = found
        names.setdefault((item_type, key), name)
        series[(item_type, key)].append(
            _SeriesMember(entry_id, status, score, title, position, finished_on, updated_at)
        )
    by_id = {candidate.entry_id: candidate for candidate in candidates}
    for (item_type, key), members in series.items():
        domain = by_type[item_type]
        flags = {status.value: status for status in domain.statuses}
        engaged = [
            m
            for m in members
            if m.status in flags and (flags[m.status].finished or flags[m.status].in_progress)
        ]
        waiting = [m for m in members if m.entry_id in by_id]
        if not engaged or not waiting:
            continue
        last = max(engaged, key=_series_order)
        dropped = [m for m in members if m.status in flags and flags[m.status].abandoned]
        if any(_series_order(m) > _series_order(last) for m in dropped):
            continue
        scores = [m.score for m in engaged if m.score is not None]
        mean = sum(scores) / len(scores) if scores else None
        if mean is not None and mean < SERIES_MIN_MEAN:
            continue
        if last.position is not None:
            # After the last one by place; a waiting one with no place may be anywhere.
            reached = last.position
            waiting = [m for m in waiting if m.position is None or m.position > reached]
            if not waiting:
                continue
        nxt = min(waiting, key=lambda m: (m.position is None, m.position or 0.0, m.entry_id))
        factor = 1.0 if mean is None else min(1.25, mean / SERIES_FULL_AT)
        if flags[last.status].in_progress:
            factor *= SERIES_UNDER_WAY
        by_id[nxt.entry_id].signals.append(
            (
                "series",
                SERIES_WEIGHT * factor,
                _series_reason(domain, names[(item_type, key)], last, flags),
            )
        )


def _series_order(member: _SeriesMember) -> tuple[float, str, str]:
    """Latest in the series: by place when known, else by finish, else by last change."""
    return (
        member.position if member.position is not None else -1.0,
        member.finished_on or "",
        member.updated_at or "",
    )


def _series_reason(domain: Domain, name: str, last: _SeriesMember, flags: dict[str, Any]) -> str:
    which = (
        _place(domain, last.position)
        if last.position is not None
        else _SERIES_IN_TITLE.sub("", last.title).strip()
    )
    if flags[last.status].in_progress:
        return f"Next in {name}; you're on {which} now"
    if last.score is not None:
        return f"Next in {name}; you gave {which} {_article(last.score)} {last.score}"
    return f"Next in {name} after {which}"


def _article(score: int) -> str:
    """ "an 8", "an 11", "an 18"; "a" before every other score."""
    return "an" if score in (8, 11, 18) else "a"


def _recency(day: str | None, today: date) -> float:
    try:
        then = date.fromisoformat(str(day)[:10])
    except (TypeError, ValueError):
        return AFFINITY_FLOOR
    years = max(0.0, (today - then).days / 365.25)
    return max(AFFINITY_FLOOR, float(0.5 ** (years / AFFINITY_HALF_LIFE_YEARS)))


def _affinity_signal(
    connection: Connection,
    user_id: int,
    domains: list[Domain],
    candidates: list[_Candidate],
    today: date,
) -> None:
    """Lift waiting entries carrying a subject the person has lately scored high."""
    # One `json_each` per (type, field), so each document is read once per field.
    paths = [
        (domain.item_type, f"$.{name}")
        for domain in domains
        for name in domain.ranking.affinity_fields
    ]
    if not paths:
        return
    params: dict[str, Any] = {"user": user_id}
    sources = []
    for index, (item_type, path) in enumerate(paths):
        params[f"type{index}"] = item_type
        params[f"path{index}"] = path
        sources.append(f"SELECT :type{index} AS type, :path{index} AS path")
    fields = " UNION ALL ".join(sources)
    planned = _in("s", sorted({value for domain in domains for value in _planned(domain)}), params)
    waiting_ids = {candidate.entry_id for candidate in candidates}
    carried: dict[int, set[str]] = defaultdict(set)
    for entry_id, value in connection.execute(
        text(
            f"WITH fields AS ({fields}) SELECT e.id, j.value FROM entries e"
            " JOIN items i ON i.id = e.item_id JOIN fields f ON f.type = i.type,"
            " json_each(i.metadata, f.path) j"
            f" WHERE e.user_id = :user AND e.status IN ({planned}) AND j.type = 'text'"
        ),
        params,
    ).all():
        if entry_id in waiting_ids:
            carried[entry_id].add(normalize_text(value))
    if not carried:
        return
    # The baseline is the person's own recent taste in that library, weighted alike:
    # when every score lately is higher, a subject is not lifted for sharing in it.
    baseline: dict[str, _Taste] = {}
    types = _in("t", sorted({item_type for item_type, _path in paths}), params)
    for item_type, score, month, count in connection.execute(
        text(
            "SELECT i.type, e.score, substr(coalesce(e.date_finished, e.date_added), 1, 7),"
            " count(*) FROM entries e JOIN items i ON i.id = e.item_id"
            f" WHERE e.user_id = :user AND e.score IS NOT NULL AND i.type IN ({types})"
            " GROUP BY 1, 2, 3"
        ),
        params,
    ).all():
        _tally(baseline.setdefault(item_type, _Taste(item_type)), score, month, count, today)
    stats: dict[tuple[str, str], _Taste] = {}
    for item_type, value, score, month, count in connection.execute(
        text(
            f"WITH fields AS ({fields}) SELECT i.type, j.value, e.score,"
            " substr(coalesce(e.date_finished, e.date_added), 1, 7), count(DISTINCT e.id)"
            " FROM entries e JOIN items i ON i.id = e.item_id JOIN fields f ON f.type = i.type,"
            " json_each(i.metadata, f.path) j"
            " WHERE e.user_id = :user AND e.score IS NOT NULL AND j.type = 'text'"
            " GROUP BY 1, 2, 3, 4"
        ),
        params,
    ).all():
        key = normalize_text(value)
        name = _subject_name(value)
        if key and name and item_type in baseline:
            _tally(
                stats.setdefault((item_type, key), _Taste(name)),
                score,
                month,
                count,
                today,
            )
    for candidate in candidates:
        base = baseline.get(candidate.item_type)
        if base is None or not base.weight:
            continue
        usual = base.weighted / base.weight
        best: tuple[float, str] | None = None
        # Sorted, so two subjects lifting alike always name the same one.
        for key in sorted(carried.get(candidate.entry_id, ())):
            taste = stats.get((candidate.item_type, key))
            # A subject on most of what was scored ("Fiction") says nothing of taste.
            if (
                taste is None
                or taste.rated < AFFINITY_MIN_RATED
                or taste.rated > AFFINITY_MAX_SHARE * base.rated
            ):
                continue
            lift = (taste.weighted - usual * taste.weight) / (taste.weight + AFFINITY_SHRINK)
            points = min(AFFINITY_CAP, AFFINITY_WEIGHT * lift)
            if points < AFFINITY_MIN_LIFT or (best is not None and points <= best[0]):
                continue
            plural = DOMAINS[candidate.item_type].plural_label.lower()
            mean = taste.total / taste.rated
            best = (points, f"You rate {taste.name} {mean:.1f} across {taste.rated} {plural}")
        if best is not None:
            candidate.signals.append(("affinity", *best))


def _subject_name(value: str) -> str | None:
    """A stored subject as a reason can say it, or None when it names nothing.

    Catalogues file books under paths in capitals ("FICTION / Horror") and under
    "General", alone or at the end of a path ("Fiction / General"); the first reads
    as "Fiction / Horror", the second is no subject at all (the 3.0 rehearsal on the
    owner's library showed "You rate General 6.9 across 7 books").
    """
    parts = [part.strip() for part in value.split("/") if part.strip()]
    if not parts or normalize_text(parts[-1]) == "general":
        return None
    return " / ".join(
        part.capitalize() if part.isupper() and len(part) > 1 else part for part in parts
    )


def _tally(taste: _Taste, score: int, month: str | None, count: int, today: date) -> None:
    weight = _recency(f"{month}-01" if month else None, today) * count
    taste.rated += count
    taste.total += score * count
    taste.weighted += weight * score
    taste.weight += weight


def _goal_signal(
    connection: Connection,
    user_id: int,
    domains: list[Domain],
    candidates: list[_Candidate],
    today: date,
) -> None:
    """Lift a library short of its goal's pace. The words never say *behind* (DEC-169)."""
    goals = connection.execute(
        text("SELECT item_type, count, period FROM goals WHERE user_id = :user"),
        {"user": user_id},
    ).all()
    if not goals:
        return
    done: dict[str, int] = dict(
        connection.execute(  # type: ignore[arg-type]
            text(
                "SELECT i.type, count(*) FROM entries e JOIN items i ON i.id = e.item_id"
                " WHERE e.user_id = :user AND e.date_finished LIKE :prefix GROUP BY 1"
            ),
            {"user": user_id, "prefix": f"{today.year:04d}-%"},
        ).all()
    )
    start = date(today.year, 1, 1)
    elapsed = ((today - start).days + 1) / ((date(today.year + 1, 1, 1) - start).days)
    ranked_types = {domain.item_type for domain in domains}
    lifts: dict[str, tuple[float, str]] = {}
    for item_type, count, period in goals:
        domain = DOMAINS.get(item_type)
        if domain is None or item_type not in ranked_types:
            continue
        target = count * 12 if period == "month" else count
        finished = done.get(item_type, 0)
        short = target * elapsed - finished
        if short < 1:
            continue
        monthly = target / 12
        points = GOAL_WEIGHT * min(1.0, short / max(1.0, monthly))
        plural = domain.plural_label.lower()
        lifts[item_type] = (points, f"Toward {target} {plural} this year; {finished} so far")
    for candidate in candidates:
        if candidate.item_type in lifts:
            candidate.signals.append(("goal", *lifts[candidate.item_type]))


def _similarity_signal(
    connection: Connection,
    user_id: int,
    domains: list[Domain],
    candidates: list[_Candidate],
    model: str,
) -> None:
    """Lift what stands closest to the person's best-scored in that library.

    The best-scored are up to `SIMILARITY_LIKED` entries scored above the person's
    mean there, highest first; what they share is their vectors' mean. Each waiting
    entry with a vector is measured against it, and lifted by how far it stands from
    the pile's median toward the closest. The reason names the one scored work it is
    nearest. Stored vectors only: nothing is asked of the endpoint here.
    """
    by_type: dict[str, list[_Candidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.item_id is not None:
            by_type[candidate.item_type].append(candidate)
    for domain in domains:
        waiting = by_type.get(domain.item_type)
        if not waiting or len(waiting) < SIMILARITY_MIN_PILE:
            continue
        params = {"user": user_id, "type": domain.item_type, "liked": SIMILARITY_LIKED}
        liked = connection.execute(
            text(
                "SELECT e.item_id, i.title, e.score FROM entries e"
                " JOIN items i ON i.id = e.item_id"
                " WHERE e.user_id = :user AND i.type = :type AND e.score IS NOT NULL"
                " AND e.score > (SELECT avg(e2.score) FROM entries e2"
                "  JOIN items i2 ON i2.id = e2.item_id"
                "  WHERE e2.user_id = :user AND i2.type = :type AND e2.score IS NOT NULL)"
                " ORDER BY e.score DESC, e.date_finished DESC, e.id LIMIT :liked"
            ),
            params,
        ).all()
        if not liked:
            continue
        vectors = load_vectors(
            connection,
            model,
            [int(row[0]) for row in liked] + [int(c.item_id) for c in waiting if c.item_id],
        )
        loved = [
            (vectors[int(row[0])], str(row[1]), int(row[2]))
            for row in liked
            if int(row[0]) in vectors
        ]
        shared = centroid(vector for vector, _title, _score in loved)
        if shared is None:
            continue
        measured = [
            (similarity(shared, vectors[candidate.item_id]), candidate)
            for candidate in waiting
            if candidate.item_id in vectors
        ]
        if len(measured) < SIMILARITY_MIN_PILE:
            continue
        median = statistics.median(score for score, _candidate in measured)
        closest = max(score for score, _candidate in measured)
        if closest - median <= 1e-9:
            continue
        measured.sort(key=lambda pair: (-pair[0], pair[1].entry_id))
        for score, candidate in measured[:SIMILARITY_TOP]:
            lift = (score - median) / (closest - median)
            if lift < SIMILARITY_MIN_LIFT:
                break
            assert candidate.item_id is not None
            own = vectors[candidate.item_id]
            _vector, title, rated = max(loved, key=lambda row: similarity(own, row[0]))
            candidate.signals.append(
                (
                    "similarity",
                    SIMILARITY_WEIGHT * lift,
                    f"Close to what you scored {rated}: {title}",
                )
            )


def _day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _waiting_signal(candidate: _Candidate, today: date) -> None:
    added = _day(candidate.date_added)
    if added is None:
        return
    years = max(0.0, (today - added).days / 365.25)
    points = WAITING_PER_YEAR * min(years, WAITING_CAP_YEARS)
    candidate.signals.append(("waiting", points, f"Waiting since {added:%b %Y}"))


def _set_aside_signal(candidate: _Candidate, today: date) -> None:
    """Started once and back on the pile: pushed down for a while after the last change."""
    started = _day(candidate.date_started)
    changed = _day(candidate.updated_at)
    if started is None or changed is None:
        return
    days = (today - changed).days
    if days >= SET_ASIDE_DAYS:
        return
    points = -SET_ASIDE_WEIGHT * (1 - max(0, days) / SET_ASIDE_DAYS)
    candidate.signals.append(
        ("set_aside", points, f"Started {started.day} {started:%b %Y}, then set aside")
    )
