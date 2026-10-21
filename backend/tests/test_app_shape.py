"""`create_app` was split into `book_tracker.app` in Sprint 088. This holds the split to
the shape the application had before it: the same routes in the same order, the same
middleware in the same order, the same exception handlers. The OpenAPI document is held
separately by `make openapi-check`."""

import json
from pathlib import Path

from book_tracker.config import Settings
from book_tracker.main import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "app_shape.json"


def app_shape(tmp_path: Path) -> dict[str, object]:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(
        Settings(data_dir=tmp_path, static_dir=static, user_agent_contact="test@example.invalid")
    )
    return {
        "routes": [
            [getattr(route, "path", ""), sorted(getattr(route, "methods", None) or [])]
            for route in app.routes
        ],
        "middleware": [
            getattr(middleware.kwargs.get("dispatch"), "__name__", middleware.cls.__name__)
            for middleware in app.user_middleware
        ],
        "exception_handlers": sorted(
            key if isinstance(key, int) else key.__name__ for key in app.exception_handlers
        ),
    }


def test_the_application_keeps_its_shape(tmp_path: Path) -> None:
    assert app_shape(tmp_path) == json.loads(FIXTURE.read_text(encoding="utf-8"))


if __name__ == "__main__":  # `python tests/test_app_shape.py` rewrites the fixture
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        FIXTURE.write_text(json.dumps(app_shape(Path(directory)), indent=1) + "\n")
