import json
import os

CONFIG_FILE = "data/guild_config.json"

def load_guild_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_guild_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_guild_state(guild_id):
    config = load_guild_config()
    return config.get(str(guild_id), {}).get("state", {})

def set_guild_state(guild_id, state_data):
    config = load_guild_config()
    guild_id_str = str(guild_id)
    if guild_id_str not in config:
        config[guild_id_str] = {}
    config[guild_id_str]["state"] = state_data
    save_guild_config(config)

def set_guild_channel(guild_id, channel_id):
    config = load_guild_config()
    guild_id_str = str(guild_id)
    if guild_id_str not in config:
        config[guild_id_str] = {}
    config[guild_id_str]["channel_id"] = channel_id
    save_guild_config(config)

def set_guild_schedule(guild_id, hour, minute, timezone):
    config = load_guild_config()
    guild_id_str = str(guild_id)
    if guild_id_str not in config:
        config[guild_id_str] = {}
    config[guild_id_str]["hour"] = hour
    config[guild_id_str]["minute"] = minute
    config[guild_id_str]["timezone"] = timezone
    save_guild_config(config)