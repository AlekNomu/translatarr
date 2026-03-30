"""API tests for /api/settings."""

from __future__ import annotations

from translatarr_web.settings import DEFAULT_SETTINGS


class TestGetSettings:
    def test_returns_defaults(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        data = r.get_json()
        assert data["settings"]["target_lang"] == DEFAULT_SETTINGS["target_lang"]

    def test_includes_whisper_model_info(self, client):
        r = client.get("/api/settings")
        data = r.get_json()
        assert "whisper_models" in data
        assert "medium" in data["whisper_models"]
        assert "description" in data["whisper_models"]["medium"]

    def test_whisper_model_descriptions_mention_vram(self, client):
        r = client.get("/api/settings")
        models = r.get_json()["whisper_models"]
        for key, info in models.items():
            assert "VRAM" in info["description"], f"No VRAM info for model '{key}'"


class TestUpdateSettings:
    def test_update_single_setting(self, client):
        r = client.put("/api/settings", json={"target_lang": "es"})
        assert r.status_code == 200
        assert r.get_json()["target_lang"] == "es"

    def test_update_persists(self, client):
        client.put("/api/settings", json={"workers": "8"})
        r = client.get("/api/settings")
        assert r.get_json()["settings"]["workers"] == "8"

    def test_update_multiple(self, client):
        client.put("/api/settings", json={"target_lang": "de", "whisper_model": "small"})
        r = client.get("/api/settings")
        s = r.get_json()["settings"]
        assert s["target_lang"] == "de"
        assert s["whisper_model"] == "small"

    def test_empty_body_returns_400(self, client):
        r = client.put("/api/settings", data="not json", content_type="text/plain")
        assert r.status_code == 400
