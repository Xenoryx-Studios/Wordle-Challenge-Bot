import asyncio

import pytest

from core import guild_config, wordle_utils


@pytest.fixture(autouse=True)
def isolated_guild_config(tmp_path, monkeypatch):
    """Redirect guild config storage to a scratch file per test, and give
    each test its own lock so it binds cleanly to that test's event loop
    instead of a stale one from a previous test."""
    config_path = tmp_path / "guild_config.json"
    monkeypatch.setattr(guild_config, "CONFIG_FILE", str(config_path))
    monkeypatch.setattr(guild_config, "_lock", asyncio.Lock())
    yield config_path


@pytest.fixture(autouse=True)
def clear_word_list_cache():
    wordle_utils._word_list_cache.clear()
    yield
    wordle_utils._word_list_cache.clear()


@pytest.fixture
def word_list_file(tmp_path):
    def _make(words):
        import json

        path = tmp_path / "words.json"
        path.write_text(json.dumps(words), encoding="utf-8")
        return str(path)

    return _make
