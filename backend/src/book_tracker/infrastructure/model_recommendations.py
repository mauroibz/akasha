"""A hosted language model as a recommendation source (Sprint 135, DEC-183 point 7, DEC-187).

One round is one request: a compact prompt built from the seed (or, with no seed,
the person's taste profile) for one library, answered as strict JSON with up to
eight `{title, creator, year, reason}` items. The answer is validated here; a reply
that is not that list fails the round with the reason.

A model names works it may have invented, and carries no identifiers. So its
candidates are **shown only after the domain resolves them**: the source declares
`resolved_only`, the round resolves every candidate (not only the first few)
through the domain's own providers under their budgets, and a screen shows only
the ones found. An unresolved pick is stored and never shown.

**What is sent** is titles, creators, years and scores, and nothing else: no notes,
reviews, tags, dates, formats, places or identifiers. `TasteProfile` already holds
only those; the seed's other fields (`metadata`, `external_ids`) are never read.
The library this asks about is named by the domain's `source_options["model"]`
(`kind`, `creator`), so this module never asks which domain it holds.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from book_tracker.domain.normalization import normalize_text
from book_tracker.domain.recommendations import (
    Candidate,
    Seed,
    SourceError,
    TasteEntry,
    TasteProfile,
)
from book_tracker.infrastructure.model_clients import PROVIDER_LABELS, ModelClient

NAME = "model"
LABEL = "Model"
#: At most this many suggestions are asked for, whatever the round's limit.
MAX_SUGGESTIONS = 8
#: How many lines of each part of the taste profile a prompt carries.
PROFILE_LINES = 12
#: What a screen says the source sends; the prompt test holds it to this.
SENDS = "Titles, creators, years and your scores from this library; nothing else."
NOT_CONFIGURED_HINT = (
    "The model source is not configured. Set AKASHA_RECS_MODEL_KEY (or ANTHROPIC_API_KEY"
    " for the default provider, Claude) in the server's environment and restart;"
    " AKASHA_RECS_MODEL_PROVIDER=gemini or openai chooses another kind of API."
)
#: A reason the model left out.
DEFAULT_REASON = "Suggested by the model"

_TITLE_CHARACTERS = 300
_CREATOR_CHARACTERS = 200
_REASON_CHARACTERS = 280
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")

SYSTEM = (
    "You suggest {kind} to one person, for their own library. Answer with JSON only,"
    ' exactly this shape: {{"suggestions": [{{"title": string, "creator": string,'
    ' "year": integer, "reason": string}}]}}, with at most {limit} items.'
    " Every item must be a real, published work you are confident exists; never"
    " invent one. title is the title it is best known by; creator is its {creator};"
    ' year is its first release year. Use "" for a creator and 0 for a year you are'
    " not sure of. reason is one short sentence, under twenty words, on why this"
    " person would like it. Never suggest anything listed as already known, turned"
    " down or waiting."
)


def _line(entry: TasteEntry, *, score: bool = True) -> str:
    text = entry.title
    if entry.creator:
        text += f" — {entry.creator}"
    if entry.year:
        text += f", {entry.year}"
    if score and entry.score is not None:
        text += f" ({entry.score}/10)"
    return f"- {text}"


def _section(heading: str, entries: Sequence[TasteEntry], *, score: bool = True) -> list[str]:
    if not entries:
        return []
    return [heading, *(_line(entry, score=score) for entry in entries[:PROFILE_LINES])]


def build_prompt(seed: Seed, profile: TasteProfile, limit: int) -> tuple[str, str]:
    """The system prompt and the question, from titles, creators, years and scores."""
    kind = seed.options.get("kind") or seed.item_type
    creator = seed.options.get("creator") or "creator"
    system = SYSTEM.format(kind=kind, creator=creator, limit=limit)
    lines: list[str] = []
    if not seed.is_profile and seed.title:
        about = TasteEntry(seed.title, seed.year, seed.creators[0] if seed.creators else None)
        lines += [f"Suggest {kind} like this one:", _line(about, score=False), ""]
    else:
        lines += [f"Suggest {kind} this person would like, from their taste below.", ""]
    for heading, entries, scored in (
        ("Their highest scores:", profile.top_scored, True),
        ("Recently finished:", profile.recent_finishes, True),
        ("Turned down before (do not suggest):", profile.dismissed, False),
        ("Already waiting on their list (do not suggest):", profile.waiting, False),
    ):
        part = _section(heading, entries, score=scored)
        if part:
            lines += [*part, ""]
    lines.append(f"Up to {limit} suggestions, as the JSON described.")
    return system, "\n".join(lines)


def _text(value: object, characters: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:characters] if cleaned else None


def _year(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, int) and 1 <= value <= 2100:
        return value
    return None


def parse_reply(text: str, limit: int, label: str = LABEL) -> list[Candidate]:
    """The candidates in a reply, or a `SourceError` when it is not the list asked for.

    Strict about the shape (a JSON object holding a `suggestions` list, or the bare
    list), forgiving about one item: an item without a title is skipped. A reply
    whose items are all unusable is malformed, as is one that is not JSON at all.
    """
    malformed = SourceError(
        f"{label} answered something other than the list it was asked for", code="malformed"
    )
    try:
        decoded: Any = json.loads(_FENCE.sub("", text.strip()))
    except (json.JSONDecodeError, TypeError):
        raise malformed from None
    items = decoded.get("suggestions") if isinstance(decoded, Mapping) else decoded
    if not isinstance(items, list):
        raise malformed
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        title = _text(item.get("title"), _TITLE_CHARACTERS)
        if title is None or normalize_text(title) in seen:
            continue
        seen.add(normalize_text(title))
        candidates.append(
            Candidate(
                title=title,
                year=_year(item.get("year")),
                creator=_text(item.get("creator"), _CREATOR_CHARACTERS),
                reason=_text(item.get("reason"), _REASON_CHARACTERS) or DEFAULT_REASON,
            )
        )
        if len(candidates) == limit:
            break
    if items and not candidates:
        raise malformed
    return candidates


class ModelRecommendations:
    """One question to a hosted model per round, its answer resolved before it is shown."""

    name = NAME
    label = LABEL
    #: A model's picks are shown only once the domain found them (DEC-183 point 7).
    resolved_only = True
    retention = None
    attribution = None

    def __init__(self, client: ModelClient) -> None:
        self.client = client

    @property
    def about(self) -> dict[str, str]:
        """What Settings says: which kind of API, which model, and what is sent."""
        return {
            "provider": self.client.provider,
            "provider_label": PROVIDER_LABELS.get(self.client.provider, self.client.provider),
            "model": self.client.model,
            "sends": SENDS,
        }

    async def select(self, seed: Seed, profile: TasteProfile, limit: int) -> list[Candidate]:
        wanted = max(1, min(limit, MAX_SUGGESTIONS))
        system, prompt = build_prompt(seed, profile, wanted)
        reply = await self.client.complete(system, prompt)
        label = PROVIDER_LABELS.get(self.client.provider, LABEL)
        return parse_reply(reply, wanted, label)
