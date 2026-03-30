"""API tests for /api/series and /api/movies."""

from __future__ import annotations

from pathlib import Path

from tests.web.conftest import insert_episode, insert_movie


class TestSeriesAPI:
    def test_empty_list(self, client):
        r = client.get("/api/series")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_lists_series_grouped(self, client, db):
        insert_episode(db, series_name="Breaking Bad", season=1, episode=1,
                       file_path="/tv/BB/S01E01.mkv", has_target_srt=1)
        insert_episode(db, series_name="Breaking Bad", season=1, episode=2,
                       file_path="/tv/BB/S01E02.mkv", has_target_srt=0)
        insert_episode(db, series_name="Better Call Saul", season=1, episode=1,
                       file_path="/tv/BCS/S01E01.mkv", has_target_srt=0)

        r = client.get("/api/series")
        data = r.get_json()
        assert len(data) == 2
        bb = next(s for s in data if s["series_name"] == "Breaking Bad")
        assert bb["episode_count"] == 2
        assert bb["subtitled_count"] == 1

    def test_detail_returns_episodes(self, client, db):
        insert_episode(db, series_name="Show", season=1, episode=1,
                       file_path="/tv/Show/S01E01.mkv")
        insert_episode(db, series_name="Show", season=1, episode=2,
                       file_path="/tv/Show/S01E02.mkv")

        r = client.get("/api/series/Show")
        assert r.status_code == 200
        data = r.get_json()
        assert data["series_name"] == "Show"
        assert len(data["episodes"]) == 2

    def test_detail_unknown_series_returns_404(self, client):
        r = client.get("/api/series/Unknown")
        assert r.status_code == 404

    def test_generate_queues_only_missing(self, client, db, app):
        insert_episode(db, series_name="Show", season=1, episode=1,
                       file_path="/tv/Show/S01E01.mkv", has_target_srt=0)
        insert_episode(db, series_name="Show", season=1, episode=2,
                       file_path="/tv/Show/S01E02.mkv", has_target_srt=1)

        r = client.post("/api/series/Show/generate")
        assert r.status_code == 202
        data = r.get_json()
        # Only episode 1 is missing subtitle
        assert data["queued"] == 1
        assert len(data["task_ids"]) == 1

    def test_generate_episode_queues_task(self, client, db, app):
        ep_id = insert_episode(db, series_name="Show", season=1, episode=1,
                               file_path="/tv/Show/S01E01.mkv")

        r = client.post(f"/api/series/Show/episodes/{ep_id}/generate")
        assert r.status_code == 202
        app.extensions["task_manager"].submit_subtitle.assert_called_once_with(ep_id)


class TestSeriesDeleteSubtitle:
    def test_delete_episode_subtitle_clears_db(self, client, db):
        ep_id = insert_episode(
            db, series_name="Show", season=1, episode=1,
            file_path="/tv/Show/S01E01.mkv",
            has_target_srt=1, target_srt_path="/tv/Show/S01E01.fr.srt",
        )
        r = client.delete(f"/api/series/Show/episodes/{ep_id}/subtitle")
        assert r.status_code == 200
        assert Path(r.get_json()["deleted"]) == Path("/tv/Show/S01E01.fr.srt")
        row = db.execute("SELECT has_target_srt, target_srt_path FROM media_items WHERE id = ?", (ep_id,)).fetchone()
        assert row["has_target_srt"] == 0
        assert row["target_srt_path"] is None

    def test_delete_episode_subtitle_not_found(self, client, db):
        ep_id = insert_episode(db, series_name="Show", season=1, episode=1,
                               file_path="/tv/Show/S01E01.mkv", has_target_srt=0)
        r = client.delete(f"/api/series/Show/episodes/{ep_id}/subtitle")
        assert r.status_code == 404

    def test_delete_episode_subtitle_records_history(self, client, db):
        ep_id = insert_episode(
            db, series_name="Show", season=1, episode=1,
            file_path="/tv/Show/S01E01.mkv",
            has_target_srt=1, target_srt_path="/tv/Show/S01E01.fr.srt",
        )
        client.delete(f"/api/series/Show/episodes/{ep_id}/subtitle")
        row = db.execute("SELECT action FROM history WHERE media_id = ?", (ep_id,)).fetchone()
        assert row["action"] == "deleted"

    def test_delete_season_subtitle(self, client, db):
        insert_episode(db, series_name="Show", season=1, episode=1,
                       file_path="/tv/Show/S01E01.mkv",
                       has_target_srt=1, target_srt_path="/tv/Show/S01E01.fr.srt")
        insert_episode(db, series_name="Show", season=1, episode=2,
                       file_path="/tv/Show/S01E02.mkv",
                       has_target_srt=1, target_srt_path="/tv/Show/S01E02.fr.srt")
        r = client.delete("/api/series/Show/seasons/1/subtitle")
        assert r.status_code == 200
        assert r.get_json()["count"] == 2

    def test_delete_season_subtitle_not_found(self, client, db):
        r = client.delete("/api/series/Show/seasons/1/subtitle")
        assert r.status_code == 404

    def test_delete_series_subtitle(self, client, db):
        insert_episode(db, series_name="Show", season=1, episode=1,
                       file_path="/tv/Show/S01E01.mkv",
                       has_target_srt=1, target_srt_path="/tv/Show/S01E01.fr.srt")
        insert_episode(db, series_name="Show", season=2, episode=1,
                       file_path="/tv/Show/S02E01.mkv",
                       has_target_srt=1, target_srt_path="/tv/Show/S02E01.fr.srt")
        r = client.delete("/api/series/Show/subtitle")
        assert r.status_code == 200
        assert r.get_json()["count"] == 2

    def test_delete_series_subtitle_not_found(self, client, db):
        r = client.delete("/api/series/Unknown/subtitle")
        assert r.status_code == 404


class TestMoviesAPI:
    def test_empty_list(self, client):
        r = client.get("/api/movies")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_lists_movies(self, client, db):
        insert_movie(db, title="Inception", year=2010)
        insert_movie(db, title="Dune", year=2021,
                     file_path="/movies/Dune (2021).mkv")

        r = client.get("/api/movies")
        data = r.get_json()
        assert len(data) == 2
        titles = {m["title"] for m in data}
        assert "Inception" in titles

    def test_detail(self, client, db):
        mid = insert_movie(db, title="Inception", year=2010)
        r = client.get(f"/api/movies/{mid}")
        assert r.status_code == 200
        assert r.get_json()["title"] == "Inception"

    def test_detail_not_found(self, client):
        r = client.get("/api/movies/9999")
        assert r.status_code == 404

    def test_generate_queues_task(self, client, db, app):
        mid = insert_movie(db, title="Inception", year=2010)
        r = client.post(f"/api/movies/{mid}/generate")
        assert r.status_code == 202
        app.extensions["task_manager"].submit_subtitle.assert_called_once_with(mid)


class TestMoviesDeleteSubtitle:
    def test_delete_subtitle_clears_db(self, client, db):
        mid = insert_movie(db, has_target_srt=1, target_srt_path="/movies/Inception.fr.srt")
        r = client.delete(f"/api/movies/{mid}/subtitle")
        assert r.status_code == 200
        assert Path(r.get_json()["deleted"]) == Path("/movies/Inception.fr.srt")
        row = db.execute("SELECT has_target_srt, target_srt_path FROM media_items WHERE id = ?", (mid,)).fetchone()
        assert row["has_target_srt"] == 0
        assert row["target_srt_path"] is None

    def test_delete_subtitle_not_found(self, client, db):
        mid = insert_movie(db, has_target_srt=0)
        r = client.delete(f"/api/movies/{mid}/subtitle")
        assert r.status_code == 404

    def test_delete_subtitle_records_history(self, client, db):
        mid = insert_movie(db, has_target_srt=1, target_srt_path="/movies/Inception.fr.srt")
        client.delete(f"/api/movies/{mid}/subtitle")
        row = db.execute("SELECT action FROM history WHERE media_id = ?", (mid,)).fetchone()
        assert row["action"] == "deleted"
