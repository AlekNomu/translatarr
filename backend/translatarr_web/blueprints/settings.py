"""
/api/settings — read and update application settings.
"""

from __future__ import annotations

import json
import string
import sys
import urllib.error
import urllib.request
from pathlib import Path

from flask import Blueprint, jsonify, request

from translatarr_web.database import get_db
from translatarr_web.settings import (
    WHISPER_MODEL_INFO,
    load_settings,
    save_settings,
)

bp = Blueprint("settings", __name__, url_prefix="/api/settings")

_SUPPORTED_SERVICES = {"sonarr", "radarr", "jellyfin"}


# ─────────────────────────────────────────────────────────────────────────────
# Settings CRUD
# ─────────────────────────────────────────────────────────────────────────────

@bp.route("", methods=["GET"])
def get_settings():
    settings = load_settings(get_db())
    return jsonify({
        "settings": settings,
        "whisper_models": WHISPER_MODEL_INFO,
    })


@bp.route("", methods=["PUT"])
def update_settings():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "JSON body required"}), 400

    save_settings(get_db(), data)
    return jsonify(load_settings(get_db()))


def _list_windows_drives():
    drives = [
        {"name": f"{d}:\\", "path": f"{d}:\\"}
        for d in string.ascii_uppercase
        if Path(f"{d}:\\").exists()
    ]
    return jsonify({"current": "", "parent": None, "dirs": drives})


@bp.route("/browse", methods=["GET"])
def browse_path():
    path = request.args.get("path", "")

    if sys.platform == "win32" and path in ("", "/"):
        return _list_windows_drives()

    p = Path(path) if path else Path("/")
    if not p.is_dir():
        if sys.platform == "win32":
            return _list_windows_drives()
        p = Path("/")

    try:
        dirs = sorted(
            [{"name": d.name, "path": str(d)} for d in p.iterdir() if d.is_dir()],
            key=lambda x: x["name"].lower(),
        )
    except PermissionError:
        dirs = []

    if sys.platform == "win32" and p.parent == p:
        # Drive root (e.g. D:\) → Up goes back to the drives list
        parent = ""
    elif p.parent == p:
        # Linux filesystem root → no parent
        parent = None
    else:
        parent = str(p.parent)

    return jsonify({"current": str(p), "parent": parent, "dirs": dirs})


# ─────────────────────────────────────────────────────────────────────────────
# Connection test
# ─────────────────────────────────────────────────────────────────────────────

def _test_arr_connection(host: str, port: str, timeout: int, api_key: str) -> dict:
    """Test connectivity to a Sonarr/Radarr-compatible *arr service."""
    url = f"http://{host}:{port}/api/v3/system/status"
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return {"ok": True, "version": data.get("version", "unknown")}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}: {exc.reason}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc.reason)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _test_jellyfin_connection(host: str, port: str, timeout: int, api_key: str) -> dict:
    """Test connectivity to a Jellyfin server."""
    url = f"http://{host}:{port}/System/Info"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f'MediaBrowser Token="{api_key}"'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return {"ok": True, "version": data.get("Version", "unknown")}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}: {exc.reason}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc.reason)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@bp.route("/<service>/test", methods=["POST"])
def test_connection(service: str):
    if service not in _SUPPORTED_SERVICES:
        return jsonify({"error": f"Unknown service: {service}"}), 404

    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({"ok": False, "error": "JSON body required"}), 400

    host = body.get("host", "").strip()
    port = body.get("port", "").strip()
    api_key = body.get("api_key", "").strip()

    if not host or not port:
        return jsonify({"ok": False, "error": "host and port are required"}), 400

    try:
        timeout = int(body.get("http_timeout", "60"))
    except ValueError:
        timeout = 60

    if service == "jellyfin":
        result = _test_jellyfin_connection(host, port, timeout, api_key)
    else:
        result = _test_arr_connection(host, port, timeout, api_key)

    return jsonify(result)
