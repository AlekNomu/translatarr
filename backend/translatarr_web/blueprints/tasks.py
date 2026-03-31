"""
/api/tasks — trigger scans, subtitle generation, and query task status.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _tm():
    return current_app.extensions["task_manager"]


@bp.route("/scan", methods=["POST"])
def trigger_scan():
    task_id = _tm().submit_scan()
    return jsonify({"task_id": task_id}), 202


@bp.route("", methods=["GET"])
def list_tasks():
    tasks = _tm().list_tasks()
    return jsonify(tasks)


@bp.route("/<task_id>", methods=["GET"])
def get_task(task_id: str):
    task = _tm().get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@bp.route("/<task_id>", methods=["DELETE"])
def cancel_task(task_id: str):
    """Cancel a queued task. Running tasks cannot be cancelled."""
    cancelled = _tm().cancel_task(task_id)
    if not cancelled:
        return jsonify({"error": "Task not found or already started"}), 409
    return jsonify({"cancelled": task_id})
