from dataclasses import dataclass
from enum import StrEnum


class MatchKind(StrEnum):
    NEW = "new"
    EXACT = "exact"
    AMBIGUOUS = "ambiguous"
    IDENTITY_CONFLICT = "identity_conflict"


@dataclass(frozen=True)
class MatchDecision:
    kind: MatchKind
    item_id: int | None = None
    candidates: tuple[int, ...] = ()


def decide_match(exact_item_ids: set[int], title_author_item_ids: set[int]) -> MatchDecision:
    exact = tuple(sorted(exact_item_ids))
    if len(exact) > 1:
        return MatchDecision(MatchKind.IDENTITY_CONFLICT, candidates=exact)
    if exact:
        return MatchDecision(MatchKind.EXACT, item_id=exact[0])
    candidates = tuple(sorted(title_author_item_ids))
    if candidates:
        return MatchDecision(MatchKind.AMBIGUOUS, candidates=candidates)
    return MatchDecision(MatchKind.NEW)
