"""M1 — typed config contract."""
import os

import pytest
from pydantic import ValidationError

import app.config
import app.config as config  # local alias for bare `config.` usage in the body


def _fresh(monkeypatch, **env):
    """Reset ORBITER_ env + the lru_cache, apply `env`, return a Settings."""
    for key in list(os.environ):
        if key.startswith("ORBITER_"):
            monkeypatch.delenv(key, raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, val)
    config.get_settings.cache_clear()
    return config.get_settings()


def test_defaults(monkeypatch):
    s = _fresh(monkeypatch, ORBITER_GEE_PROJECT="test")
    assert s.gee_project == "test"
    assert s.cors_origins == ["http://localhost:5173"]
    assert s.mapid_ttl_seconds == 21600
    assert s.max_scenes_per_composite == 25
    assert s.default_cloud_cover == 20.0
    assert s.ee_threadpool_workers == 8
    assert s.gee_high_volume is True


def test_missing_project_is_loud(monkeypatch):
    with pytest.raises(ValidationError):
        _fresh(monkeypatch)  # no ORBITER_GEE_PROJECT


def test_cors_accepts_csv(monkeypatch):
    s = _fresh(
        monkeypatch,
        ORBITER_GEE_PROJECT="test",
        ORBITER_CORS_ORIGINS="http://a.example, http://b.example",
    )
    assert s.cors_origins == ["http://a.example", "http://b.example"]


def test_cors_accepts_json(monkeypatch):
    s = _fresh(
        monkeypatch,
        ORBITER_GEE_PROJECT="test",
        ORBITER_CORS_ORIGINS='["http://c.example"]',
    )
    assert s.cors_origins == ["http://c.example"]
