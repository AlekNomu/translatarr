"""
translatarr_web.translatarr
~~~~~~~~~~~~~~~
Flask application factory and ``translatarr-web`` entry point.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import time
from pathlib import Path

from flask import Flask, send_from_directory

from translatarr_web.blueprints.history import bp as history_bp
from translatarr_web.blueprints.movies import bp as movies_bp
from translatarr_web.blueprints.series import bp as series_bp
from translatarr_web.blueprints.settings import bp as settings_bp
from translatarr_web.blueprints.system import bp as system_bp
from translatarr_web.blueprints.tasks import bp as tasks_bp
from translatarr_web.database import init_app, init_db
from translatarr_web.log_handler import WebLogHandler
from translatarr_web.scheduler import init_scheduler
from translatarr_web.settings import load_settings as _load_settings
from translatarr_web.settings import seed_defaults
from translatarr_web.task_manager import TaskManager

_DEFAULT_PORT = 6868


def create_app(config_dir: Path | None = None, _testing: bool = False) -> Flask:
    """Build and configure the Flask application."""
    if config_dir is None:
        config_dir = Path(os.environ.get("TRANSLATARR_CONFIG_DIR", "config"))
    config_dir = config_dir.resolve()
    config_dir.mkdir(parents=True, exist_ok=True)

    db_path = config_dir / "translatarr.db"

    app = Flask(__name__, static_folder=None)
    app.config["START_TIME"] = time.time()
    app.config["CONFIG_DIR"] = str(config_dir)

    # ── Database ──────────────────────────────────────────────────────────
    init_db(db_path)
    init_app(app, db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    seed_defaults(conn)

    # ── Blueprints ────────────────────────────────────────────────────────
    app.register_blueprint(settings_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(series_bp)
    app.register_blueprint(movies_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(history_bp)

    # ── Log handler for SSE streaming + console output ───────────────────
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    web_handler = WebLogHandler()
    web_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    translatarr_logger = logging.getLogger("translatarr")
    translatarr_logger.setLevel(logging.INFO)
    translatarr_logger.addHandler(web_handler)
    translatarr_logger.addHandler(console_handler)
    translatarr_logger.propagate = False
    app.extensions["web_log_handler"] = web_handler

    # ── Task manager + scheduler ──────────────────────────────────────────
    _settings = _load_settings(conn)
    conn.close()

    tm = TaskManager(app, max_workers=int(_settings.get("workers", "4")))
    app.extensions["task_manager"] = tm

    scheduler = init_scheduler(
        app, tm,
        interval_minutes=int(_settings.get("scan_interval_minutes", "60")),
        scan_on_startup=(not _testing) and _settings.get("scan_on_startup", "1") == "1",
    )
    app.extensions["scheduler"] = scheduler

    # ── SPA fallback ──────────────────────────────────────────────────────
    _static_dir = Path(__file__).parent / "static"

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path: str):
        static = _static_dir
        file = static / path
        if path and file.is_file():
            return send_from_directory(static, path)
        index = static / "index.html"
        if index.is_file():
            return send_from_directory(static, "index.html")
        return "translatarr-web: frontend not built yet. Run 'npm run build' in frontend/.", 200

    return app


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="translatarr-web",
        description="Start the translatarr web interface.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument(
        "--config-dir", type=Path, default=None,
        help="Directory for database and config (default: ./config or TRANSLATARR_CONFIG_DIR).",
    )
    args = parser.parse_args()
    app = create_app(config_dir=args.config_dir)
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
