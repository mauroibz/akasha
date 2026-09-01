"""Register Sprint 052's two-domain fixture connector in a walkthrough backend.

Sprint 052 widened the import boundary so one source may fill two libraries, and
proved it against a **test** connector rather than against IMDb — a seam proved only
by the connector it was built for is not proved (DEC-093). The walkthrough gate needs
the same connector inside a *running* application, so this module registers it and
hands the launcher a pass-through transport.

    cd backend && uv run python ../scripts/walkthrough.py \
        --replay ../scripts/walkthrough_two_domains.py

The connector is imported from `backend/tests/test_multi_domain_imports.py` rather
than redefined here, so the flow a person drives in a browser is exactly the one the
suite exercises. Its rows are invented: no fixture in this repository is cut from the
owner's private exports.

The provider boundary stays **live** — this module replays nothing. It is a `--replay`
module only because that is the launcher's one seam that runs inside the application
before a request is served.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from book_tracker.domain.registry import IMPORTERS, IMPORTERS_BY_DOMAIN  # noqa: E402
from test_multi_domain_imports import TwoDomainImporter  # noqa: E402

IMPORTER = TwoDomainImporter()
IMPORTERS[IMPORTER.name] = IMPORTER  # type: ignore[assignment]
for item_type in IMPORTER.item_types:
    IMPORTERS_BY_DOMAIN[item_type] = (*IMPORTERS_BY_DOMAIN[item_type], IMPORTER)  # type: ignore[arg-type]


def walkthrough_transport(live: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
    """Nothing is replayed: this run's providers answer for themselves."""
    return live
