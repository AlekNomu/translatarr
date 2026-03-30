"""API tests for /api/system and /api/tasks."""

from __future__ import annotations
from translatarr import __version__


class TestSystemStatus:
    def test_returns_version(self, client):
        r = client.get("/api/system/status")
        assert r.status_code == 200
        assert r.get_json()["version"] == __version__

    def test_includes_uptime(self, client):
        r = client.get("/api/system/status")
        assert "uptime_seconds" in r.get_json()

    def test_ffmpeg_check_present(self, client):
        r = client.get("/api/system/status")
        assert "ffmpeg_available" in r.get_json()

    def test_whisper_check_present(self, client):
        r = client.get("/api/system/status")
        assert "whisper_available" in r.get_json()


class TestSystemLogs:
    def test_recent_logs_empty(self, client):
        r = client.get("/api/system/logs/recent")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_recent_logs_after_emit(self, client, app):
        import logging
        logging.getLogger("translatarr").info("test log entry")
        r = client.get("/api/system/logs/recent")
        messages = [e["message"] for e in r.get_json()]
        assert any("test log entry" in m for m in messages)


class TestTasksAPI:
    def test_trigger_scan(self, client, app):
        r = client.post("/api/tasks/scan")
        assert r.status_code == 202
        assert r.get_json()["task_id"] == "scan-task-id"
        app.extensions["task_manager"].submit_scan.assert_called_once()

    def test_list_tasks_empty(self, client):
        r = client.get("/api/tasks")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_list_tasks_returns_data(self, client, app):
        app.extensions["task_manager"].list_tasks.return_value = [
            {"id": "abc", "status": "completed", "progress": 100}
        ]
        r = client.get("/api/tasks")
        assert len(r.get_json()) == 1

    def test_get_task_not_found(self, client):
        r = client.get("/api/tasks/nonexistent-id")
        assert r.status_code == 404

    def test_get_task_found(self, client, app):
        app.extensions["task_manager"].get_task.return_value = {
            "id": "abc", "status": "running", "progress": 50
        }
        r = client.get("/api/tasks/abc")
        assert r.status_code == 200
        assert r.get_json()["status"] == "running"
