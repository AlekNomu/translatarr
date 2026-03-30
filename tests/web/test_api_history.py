"""API tests for /api/history."""

from __future__ import annotations

from tests.web.conftest import insert_history


class TestHistoryAPI:
    def test_empty_history(self, client):
        r = client.get("/api/history")
        assert r.status_code == 200
        data = r.get_json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_returns_entries(self, client, db):
        insert_history(db, action="translated")
        insert_history(db, action="failed", file_path="/movies/Other.mkv")

        r = client.get("/api/history")
        data = r.get_json()
        assert data["total"] == 2

    def test_filter_by_action(self, client, db):
        insert_history(db, action="translated")
        insert_history(db, action="failed", file_path="/movies/Other.mkv")

        r = client.get("/api/history?action=translated")
        data = r.get_json()
        assert data["total"] == 1
        assert data["items"][0]["action"] == "translated"

    def test_pagination(self, client, db):
        for i in range(5):
            insert_history(db, file_path=f"/movies/Movie{i}.mkv")

        r = client.get("/api/history?per_page=2&page=1")
        data = r.get_json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1

    def test_second_page(self, client, db):
        for i in range(5):
            insert_history(db, file_path=f"/movies/Movie{i}.mkv")

        r = client.get("/api/history?per_page=2&page=2")
        data = r.get_json()
        assert len(data["items"]) == 2
        assert data["page"] == 2
