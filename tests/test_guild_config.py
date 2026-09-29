import asyncio
import json

from core import guild_config


async def test_load_returns_empty_dict_when_file_missing():
    assert await guild_config.load_guild_config() == {}


async def test_set_and_get_guild_state_roundtrip():
    state = {"word": "CRANE", "used_words": ["CRANE"], "thread_id": 42}
    await guild_config.set_guild_state(123, state)

    assert await guild_config.get_guild_state(123) == state


async def test_get_guild_state_missing_guild_returns_empty_dict():
    assert await guild_config.get_guild_state(999) == {}


async def test_set_guild_channel_and_state_do_not_clobber_each_other():
    await guild_config.set_guild_channel(1, 555)
    await guild_config.set_guild_state(1, {"word": "SLATE"})

    config = await guild_config.load_guild_config()
    assert config["1"]["channel_id"] == 555
    assert config["1"]["state"] == {"word": "SLATE"}


async def test_set_guild_timezone_stores_timezone_only():
    await guild_config.set_guild_timezone(7, "America/Toronto")

    config = await guild_config.load_guild_config()
    assert config["7"] == {"timezone": "America/Toronto"}


async def test_save_is_atomic_no_leftover_tmp_file(isolated_guild_config):
    await guild_config.set_guild_channel(1, 100)

    assert isolated_guild_config.exists()
    tmp_path = isolated_guild_config.with_suffix(isolated_guild_config.suffix + ".tmp")
    assert not tmp_path.exists()


def _read_json_sync(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def test_save_leaves_valid_json_on_disk(isolated_guild_config):
    await guild_config.set_guild_channel(1, 100)

    on_disk = await asyncio.to_thread(_read_json_sync, isolated_guild_config)
    assert on_disk["1"]["channel_id"] == 100


async def test_concurrent_writes_to_different_guilds_do_not_clobber():
    await asyncio.gather(
        *[guild_config.set_guild_channel(guild_id, 1000 + guild_id) for guild_id in range(25)]
    )

    config = await guild_config.load_guild_config()
    assert len(config) == 25
    for guild_id in range(25):
        assert config[str(guild_id)]["channel_id"] == 1000 + guild_id


async def test_get_guild_entry_returns_full_entry():
    await guild_config.set_guild_channel(5, 111)
    await guild_config.set_guild_timezone(5, "UTC")
    await guild_config.set_guild_state(5, {"word": "CRANE"})

    entry = await guild_config.get_guild_entry(5)
    assert entry == {
        "channel_id": 111,
        "timezone": "UTC",
        "state": {"word": "CRANE"},
    }


async def test_get_guild_entry_missing_guild_returns_empty_dict():
    assert await guild_config.get_guild_entry(999) == {}


async def test_stop_guild_removes_posting_settings_but_keeps_state():
    # Legacy hour/minute from the old scheduling command are cleaned up too.
    await guild_config.save_guild_config(
        {"9": {"channel_id": 222, "hour": 14, "minute": 15, "timezone": "Europe/London"}}
    )
    await guild_config.set_guild_state(9, {"word": "STARE", "used_words": ["STARE"]})

    await guild_config.stop_guild(9)

    entry = await guild_config.get_guild_entry(9)
    assert "channel_id" not in entry
    assert "hour" not in entry
    assert "minute" not in entry
    assert "timezone" not in entry
    assert entry["state"] == {"word": "STARE", "used_words": ["STARE"]}
