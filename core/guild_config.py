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


async def set_guild_theme(guild_id, theme_name):
    await _update_guild(guild_id, lambda entry: entry.update(theme=theme_name))


async def set_reminder_opt_in(guild_id, member_id, opted_in):
    """Add or remove a member from the server's Reminder opt-ins."""
    def mutate(entry):
        members = set(entry.get("reminder_members", []))
        if opted_in:
            members.add(member_id)
        else:
            members.discard(member_id)
        entry["reminder_members"] = sorted(members)

    await _update_guild(guild_id, mutate)


async def set_guild_timezone(guild_id, timezone):
    await _update_guild(guild_id, lambda entry: entry.update(timezone=timezone))


def _clear_posting_fields(entry):
    # A server with no channel_id is Stopped. hour/minute are only removed
    # as leftovers from the old scheduling command; nothing reads them.
    for key in ("channel_id", "hour", "minute", "timezone"):
        entry.pop(key, None)


async def stop_guild(guild_id):
    await _update_guild(guild_id, _clear_posting_fields)
