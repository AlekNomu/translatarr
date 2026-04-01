"""API tests for /api/settings."""

from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock, patch

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


class TestConnectionTest:
    """Tests for POST /api/settings/{service}/test."""

    _VALID_BODY = {
        "host": "192.168.1.10",
        "port": "8989",
        "http_timeout": "5",
        "api_key": "abc123",
    }

    def test_unknown_service_returns_404(self, client):
        r = client.post("/api/settings/plex/test", json=self._VALID_BODY)
        assert r.status_code == 404

    def test_missing_body_returns_400(self, client):
        r = client.post("/api/settings/sonarr/test", data="bad", content_type="text/plain")
        assert r.status_code == 400

    def test_missing_host_returns_400(self, client):
        r = client.post("/api/settings/sonarr/test", json={"port": "8989"})
        assert r.status_code == 400

    @patch("translatarr_web.blueprints.settings.urllib.request.urlopen")
    def test_sonarr_unreachable_returns_ok_false(self, mock_urlopen, client):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        r = client.post("/api/settings/sonarr/test", json=self._VALID_BODY)
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is False
        assert "error" in data

    @patch("translatarr_web.blueprints.settings.urllib.request.urlopen")
    def test_radarr_unreachable_returns_ok_false(self, mock_urlopen, client):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        body = {**self._VALID_BODY, "port": "7878"}
        r = client.post("/api/settings/radarr/test", json=body)
        assert r.status_code == 200
        assert r.get_json()["ok"] is False

    @patch("translatarr_web.blueprints.settings.urllib.request.urlopen")
    def test_jellyfin_unreachable_returns_ok_false(self, mock_urlopen, client):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        body = {**self._VALID_BODY, "port": "8096"}
        r = client.post("/api/settings/jellyfin/test", json=body)
        assert r.status_code == 200
        assert r.get_json()["ok"] is False

    @patch("translatarr_web.blueprints.settings.urllib.request.urlopen")
    def test_sonarr_success_returns_version(self, mock_urlopen, client):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"version": "4.0.1"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        r = client.post("/api/settings/sonarr/test", json=self._VALID_BODY)
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["version"] == "4.0.1"

    @patch("translatarr_web.blueprints.settings.urllib.request.urlopen")
    def test_jellyfin_success_returns_version(self, mock_urlopen, client):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"Version": "10.9.0"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        body = {**self._VALID_BODY, "port": "8096"}
        r = client.post("/api/settings/jellyfin/test", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["version"] == "10.9.0"
