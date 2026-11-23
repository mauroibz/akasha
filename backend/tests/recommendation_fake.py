"""The `fake` recommendation source: test-only, backed by a recorded JSON file.

Sprint 133 proves the pipeline (seed, select, store, enrich, answer) before any real
source exists. A real source is an adapter with this shape: one `select` per round.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from book_tracker.domain.recommendations import Candidate, Seed, TasteProfile

RECORDING = Path(__file__).parent / "fixtures" / "recommendations" / "fake_source.json"


class FakeSource:
    name = "fake"

    def __init__(self, recording: Path = RECORDING) -> None:
        self.rounds = json.loads(recording.read_text(encoding="utf-8"))["rounds"]
        self.calls: list[tuple[Seed, TasteProfile, int]] = []

    async def select(self, seed: Seed, profile: TasteProfile, limit: int) -> Sequence[Candidate]:
        self.calls.append((seed, profile, limit))
        rows = self.rounds.get(seed.title or "", self.rounds["default"])
        return [Candidate(**row) for row in rows][:limit]
