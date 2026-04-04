"""
/api/system — status, health, and log streaming endpoints.
"""

from __future__ import annotations

import platform
import subprocess
import time

from flask import Blueprint, Response, current_app, jsonify

from translatarr import __version__

try:
    import faster_whisper  # type: ignore  # noqa: F401
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False

bp = Blueprint("system", __name__, url_prefix="/api/system")


@bp.route("/status", methods=["GET"])
def status():
    app = current_app
    uptime = time.time() - app.config.get("START_TIME", time.time())

    ffmpeg_ok = _check_ffmpeg()
    whisper_ok = _check_whisper()

    return jsonify({
        "version": __version__,
        "python_version": platform.python_version(),
        "uptime_seconds": round(uptime, 1),
        "ffmpeg_available": ffmpeg_ok,
        "whisper_available": whisper_ok,
    })


def _check_ffmpeg() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return True
    except Exception:
        return False


def _check_whisper() -> bool:
    return _WHISPER_AVAILABLE


@bp.route("/logs", methods=["GET"])
def stream_logs():
    """SSE endpoint for real-time log streaming."""
    handler = current_app.extensions.get("web_log_handler")
    if not handler:
        return jsonify({"error": "Log handler not configured"}), 500
    q = handler.subscribe()
    return Response(handler.sse_generate(q), mimetype="text/event-stream")


@bp.route("/logs/recent", methods=["GET"])
def recent_logs():
    """Return the last 200 log entries as JSON."""
    handler = current_app.extensions.get("web_log_handler")
    if not handler:
        return jsonify([])
    return jsonify(handler.get_recent(200))
