"""
/api/settings — read and update application settings.
"""

from __future__ import annotations

import string
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request

from translatarr_web.settings import (
    WHISPER_MODEL_INFO,
    load_settings,
    save_settings,
)
from translatarr_web.database import get_db

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


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


@bp.route("/browse", methods=["GET"])
def browse_path():
    path = request.args.get("path", "")

    # Windows with no path → list available drives
    if sys.platform == "win32" and path in ("", "/"):
        drives = [
            {"name": f"{d}:\\", "path": f"{d}:\\"}
            for d in string.ascii_uppercase
            if Path(f"{d}:\\").exists()
        ]
        return jsonify({"current": "", "parent": None, "dirs": drives})

    p = Path(path) if path else Path("/")
    if not p.is_dir():
        # Path doesn't exist — fall back to root
        if sys.platform == "win32":
            drives = [
                {"name": f"{d}:\\", "path": f"{d}:\\"}
                for d in string.ascii_uppercase
                if Path(f"{d}:\\").exists()
            ]
            return jsonify({"current": "", "parent": None, "dirs": drives})
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
