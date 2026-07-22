#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from book_tracker.main import create_app


def render() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the deterministic OpenAPI contract")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
    generated = render()
    if args.check:
        if not destination.exists() or destination.read_text(encoding="utf-8") != generated:
            print("frontend/openapi.json is stale; run 'make openapi'")
            return 1
        return 0
    destination.write_text(generated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
