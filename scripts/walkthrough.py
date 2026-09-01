"""The tracked walkthrough launcher: one command, a fresh data dir, a ready backend.

TESTING.md's *Walkthrough reuse* section asked for this: until now every sprint's
realistic-data gate hand-rolled the same ~120 lines — temporary data directory,
lifespan driven by hand (uvicorn's own pass would undo a replay seam installed
inside it), readiness waited on the socket, graceful stop. Two runners already
carried near-copies (`walkthrough_series.py`, `walkthrough_series_050.py`).

This launcher owns that machinery and nothing else. A walkthrough *flow* — a
Playwright spec or a script — runs against the base URL it prints:

    cd backend && uv run python ../scripts/walkthrough.py
    cd backend && uv run python ../scripts/walkthrough.py --replay scripts/walkthrough_series_050.py
    cd backend && uv run python ../scripts/walkthrough.py --keep

- A fresh temporary data directory is created per run (`--keep` preserves it for
  inspection; the default cleans it up on exit).
- The backend starts on an ephemeral port, waits for readiness, and stops
  cleanly on SIGINT/SIGTERM.
- `--replay <module>` installs that module's `walkthrough_transport(live)` seam
  at the same point the series runners did: inside the lifespan, after the
  catalog is built, swapping the shared provider client's transport so every
  provider — and the enrichment handler's cover client — replays through it.
  Without `--replay` the whole boundary is live.
- The source library a flow needs is passed by the flow itself through the
  environment (`BOOK_TRACKER_WALKTHROUGH_LIBRARY`); the launcher never
  hardcodes an owner path.

The runner drives the lifespan itself (`lifespan="off"` on uvicorn) because the
replay seam is installed inside it — Sprint 050's worklog records uvicorn's own
pass re-running the lifespan and silently rebuilding every provider on a live
client.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import shutil
import signal
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))

from book_tracker.config import Settings  # noqa: E402
from book_tracker.infrastructure.providers import create_provider_client  # noqa: E402
from book_tracker.main import create_app  # noqa: E402


def load_replay(module_path: str):
    """Import a replay module and return its `walkthrough_transport` factory."""
    spec = importlib.util.spec_from_file_location("walkthrough_replay", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load replay module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, "walkthrough_transport", None)
    if factory is None:
        raise SystemExit(f"{module_path} defines no walkthrough_transport(live)")
    return factory


async def serve(args: argparse.Namespace) -> int:
    data_dir = Path(tempfile.mkdtemp(prefix="akasha-walkthrough-"))
    settings = Settings(
        data_dir=data_dir,
        user_agent_contact="walkthrough@example.invalid",
        log_level="WARNING",
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        live_transport = httpx.AsyncHTTPTransport()
        if args.replay:
            # The same seam the series runners used, one level up: swap the shared
            # client's transport inside the lifespan so every provider replays,
            # while whatever the replay module passes through stays live.
            replaying = create_provider_client(load_replay(args.replay)(live_transport))
            await app.state.provider_client.aclose()
            app.state.provider_client = replaying
            for provider in app.state.provider_catalog.values():
                provider.client = replaying
            for handler in app.state.job_runner.handlers.values():
                if hasattr(handler, "cover_client"):
                    handler.cover_client = replaying

        import uvicorn

        # lifespan="off": the lifespan is driven above, and uvicorn's own pass
        # would re-run it and rebuild every provider on a live client, silently
        # undoing the replay swap.
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="off")
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve())
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.05)
        if not server.started:
            raise SystemExit("backend did not start within 10 s")
        port = server.servers[0].sockets[0].getsockname()[1]

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        print(f"walkthrough backend on http://127.0.0.1:{port}", flush=True)
        print(f"BOOK_TRACKER_DATA_DIR={data_dir}", flush=True)
        try:
            await stop.wait()
        finally:
            server.should_exit = True
            await task
            await live_transport.aclose()
    if args.keep:
        print(f"data dir kept: {data_dir}", flush=True)
    else:
        shutil.rmtree(data_dir, ignore_errors=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--replay",
        metavar="MODULE",
        help="path to a module defining walkthrough_transport(live) to replay "
        "provider responses from fixtures; the boundary is live without it",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the temporary data directory for inspection instead of cleaning it up",
    )
    return asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
