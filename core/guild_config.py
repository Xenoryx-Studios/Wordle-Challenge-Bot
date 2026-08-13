import asyncio
import json
import os

CONFIG_FILE = "data/guild_config.json"

_lock = asyncio.Lock()


def _read_config_sync():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_config_sync(config):
    tmp_file = f"{CONFIG_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    os.replace(tmp_file, CONFIG_FILE)


async def load_guild_config():
    async with _lock:
        return await asyncio.to_thread(_read_config_sync)


async def save_guild_config(config):
    async with _lock:
        await asyncio.to_thread(_write_config_sync, config)


async def get_guild_state(guild_id):
    async with _lock:
        config = await asyncio.to_thread(_read_config_sync)
        return config.get(str(guild_id), {}).get("state", {})


async def get_guild_timezone(guild_id):
    async with _lock:
        config = await asyncio.to_thread(_read_config_sync)
        return config.get(str(guild_id), {}).get("timezone", "UTC")


async def get_guild_entry(guild_id):
    async with _lock:
        config = await asyncio.to_thread(_read_config_sync)
        return config.get(str(guild_id), {})


async def _update_guild(guild_id, mutate):
    async with _lock:
        config = await asyncio.to_thread(_read_config_sync)
        entry = config.setdefault(str(guild_id), {})
        mutate(entry)
        await asyncio.to_thread(_write_config_sync, config)


async def set_guild_state(guild_id, state_data):
    await _update_guild(guild_id, lambda entry: entry.update(state=state_data))


async def set_guild_channel(guild_id, channel_id):
    await _update_guild(guild_id, lambda entry: entry.update(channel_id=channel_id))


async def set_guild_schedule(guild_id, hour, minute, timezone):
    await _update_guild(
        guild_id,
        lambda entry: entry.update(hour=hour, minute=minute, timezone=timezone),
    )


def _clear_schedule_fields(entry):
    # channel_id must be cleared too: the scheduler defaults hour/minute/
    # timezone to midnight UTC when they're absent but channel_id is still
    # set, so leaving channel_id behind would keep auto-posting there.
    for key in ("channel_id", "hour", "minute", "timezone"):
        entry.pop(key, None)


async def clear_guild_schedule(guild_id):
    await _update_guild(guild_id, _clear_schedule_fields)
