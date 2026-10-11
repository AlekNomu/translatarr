"""Unit tests for translatarr_web.settings — settings CRUD."""

from __future__ import annotations

import sqlite3
import pytest

from translatarr.translator import DEFAULT_PROVIDER, PROVIDERS
from translatarr_web.settings import (
    DEFAULT_SETTINGS,
    WHISPER_MODEL_INFO,
    load_setting,
    load_settings,
    provider_config,
    save_settings,
    seed_defaults,
)


@pytest.fixture()
def mem_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    return conn


def test_seed_inserts_all_defaults(mem_db):
    seed_defaults(mem_db)
    rows = mem_db.execute("SELECT key FROM settings").fetchall()
    keys = {r["key"] for r in rows}
    assert keys == set(DEFAULT_SETTINGS.keys())


def test_seed_is_idempotent(mem_db):
    seed_defaults(mem_db)
    seed_defaults(mem_db)  # must not raise or duplicate
    count = mem_db.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    assert count == len(DEFAULT_SETTINGS)


def test_load_settings_returns_all(mem_db):
    seed_defaults(mem_db)
    settings = load_settings(mem_db)
    assert settings["target_lang"] == "fr"
    assert settings["whisper_model"] == "medium"


def test_load_setting_fallback(mem_db):
    # Table is empty — should return the hard-coded default
    value = load_setting(mem_db, "target_lang")
    assert value == DEFAULT_SETTINGS["target_lang"]


def test_load_setting_unknown_key(mem_db):
    assert load_setting(mem_db, "nonexistent_key") == ""


def test_save_settings_upsert(mem_db):
    seed_defaults(mem_db)
    save_settings(mem_db, {"target_lang": "es", "workers": "8"})
    assert load_setting(mem_db, "target_lang") == "es"
    assert load_setting(mem_db, "workers") == "8"


def test_env_override_load_settings(mem_db, monkeypatch):
    seed_defaults(mem_db)
    monkeypatch.setenv("MOVIES_PATH", "/data/films")
    monkeypatch.setenv("SERIES_PATH", "/data/series")
    settings = load_settings(mem_db)
    assert settings["movies_path"] == "/data/films"
    assert settings["series_path"] == "/data/series"
    # Unrelated settings must not be affected
    assert settings["target_lang"] == "fr"


def test_env_override_load_setting(mem_db, monkeypatch):
    seed_defaults(mem_db)
    monkeypatch.setenv("MOVIES_PATH", "/custom/movies")
    assert load_setting(mem_db, "movies_path") == "/custom/movies"


def test_env_override_not_set_uses_db(mem_db, monkeypatch):
    seed_defaults(mem_db)
    save_settings(mem_db, {"movies_path": "/my/movies"})
    monkeypatch.delenv("MOVIES_PATH", raising=False)
    assert load_setting(mem_db, "movies_path") == "/my/movies"


def test_whisper_model_info_has_all_models():
    expected = {"tiny", "base", "small", "medium", "large"}
    assert set(WHISPER_MODEL_INFO.keys()) == expected


def test_whisper_model_info_has_description():
    for key, info in WHISPER_MODEL_INFO.items():
        assert "label" in info, f"Missing label for {key}"
        assert "description" in info, f"Missing description for {key}"
        assert "VRAM" in info["description"], f"Missing VRAM info for {key}"


def test_seed_inserts_sonarr_radarr_jellyfin_defaults(mem_db):
    seed_defaults(mem_db)
    rows = mem_db.execute("SELECT key FROM settings").fetchall()
    keys = {r["key"] for r in rows}
    for service in ("sonarr", "radarr", "jellyfin"):
        for field in ("enabled", "host", "port", "http_timeout", "api_key"):
            key = f"{service}_{field}"
            assert key in keys, f"Missing default key: {key}"


def test_integration_defaults_values(mem_db):
    seed_defaults(mem_db)
    settings = load_settings(mem_db)
    assert settings["sonarr_host"] == "sonarr"
    assert settings["sonarr_port"] == "8989"
    assert settings["radarr_host"] == "radarr"
    assert settings["radarr_port"] == "7878"
    assert settings["jellyfin_host"] == "jellyfin"
    assert settings["jellyfin_port"] == "8096"
    for service in ("sonarr", "radarr", "jellyfin"):
        assert settings[f"{service}_enabled"] == "0"
        assert settings[f"{service}_http_timeout"] == "60"
        assert settings[f"{service}_api_key"] == ""


# ─────────────────────────────────────────────────────────────────────────────
# Translation provider settings
# ─────────────────────────────────────────────────────────────────────────────

def test_translation_provider_defaults_to_google(mem_db):
    seed_defaults(mem_db)
    assert load_settings(mem_db)["translation_provider"] == DEFAULT_PROVIDER


def test_every_provider_field_is_seeded(mem_db):
    """A provider's inputs must exist as settings or the UI cannot bind to them."""
    seed_defaults(mem_db)
    keys = {r["key"] for r in mem_db.execute("SELECT key FROM settings").fetchall()}
    for spec in PROVIDERS.values():
        for field in spec.fields:
            assert field.key in keys, f"Missing default for {spec.key}.{field.key}"


def test_toggle_fields_default_on(mem_db):
    seed_defaults(mem_db)
    settings = load_settings(mem_db)
    for spec in PROVIDERS.values():
        for field in spec.fields:
            expected = "1" if field.kind == "toggle" else ""
            assert settings[field.key] == expected


def test_provider_config_selects_only_engine_credentials(mem_db):
    seed_defaults(mem_db)
    save_settings(mem_db, {"deepl_api_key": "secret", "sonarr_api_key": "unrelated"})

    config = provider_config(load_settings(mem_db))

    assert config["deepl_api_key"] == "secret"
    assert "sonarr_api_key" not in config
    assert "movies_path" not in config


def test_provider_config_tolerates_missing_keys():
    config = provider_config({})
    assert set(config) == {f.key for s in PROVIDERS.values() for f in s.fields}
    assert all(value == "" for value in config.values())


def test_switching_provider_persists(mem_db):
    seed_defaults(mem_db)
    save_settings(mem_db, {"translation_provider": "mymemory"})
    assert load_setting(mem_db, "translation_provider") == "mymemory"
